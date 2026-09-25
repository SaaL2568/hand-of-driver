"""Integrated MediaPipe Thumb Controller (Part A) for Vehicle Simulator (Part B).

Combines the NEW MediaPipe Tasks API (hand_landmarker.task) thumb-direction tracking
with the UDP telemetry protocol to control the Pygame vehicle simulator.

Control Mapping (two independent channels, so you can steer AND accelerate at once):
----------------
[Thumb ANGLE -> Steering]   (like tilting a joystick)
  - Thumb straight UP          -> 0.0 (straight)
  - Thumb tilted/pointing LEFT -> towards -1.0 (full left at ~65 deg tilt)
  - Thumb tilted/pointing RIGHT-> towards +1.0
  - Angle is measured in pixel space (aspect-corrected) and normalised by thumb
    length, so it works the same regardless of hand size or distance to camera.

[PALM height -> Pedals]
  - Palm HIGH in frame   -> THROTTLE
  - Palm in the middle   -> Coasting
  - Palm LOW in frame    -> BRAKE
  - Uses the palm centre, not the thumb tip, so tilting the thumb to steer
    does not change the throttle.

Stabilization:
  - One Euro filter per channel: heavy smoothing when the hand is still
    (no jitter) and light smoothing when it moves fast (no lag).
  - MediaPipe VIDEO mode (temporal tracking) for stable landmarks.
  - Short hold on hand loss, then smooth decay to idle instead of snapping.
"""
import argparse
import csv
import importlib.util
import subprocess
import sys
from pathlib import Path
import time
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

from calibration import CalibrationProfile, CalibrationSession
from gesture_client import GestureClient
from gesture_commands import (GestureCommandInterpreter, YoloGestureWorker,
                              default_yolo_model_path, finger_states, pattern_from_states)


class OneEuroFilter:
    """One Euro filter (Casiez et al., CHI 2012): adaptive low-pass filter.

    Cutoff frequency rises with signal speed, so slow/still input is smoothed
    heavily while fast movements pass through with little lag.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.5, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self, value: float = None):
        self.x_prev = value
        self.dx_prev = 0.0
        self.t_prev = None

    def hold(self, value: float, t: float):
        """Pin the filter to `value` at time t, so resuming later starts smoothly from it."""
        self.x_prev, self.dx_prev, self.t_prev = value, 0.0, t

    def __call__(self, x: float, t: float) -> float:
        if self.x_prev is None or self.t_prev is None:
            self.x_prev, self.t_prev = x, t
            return x
        dt = max(1e-3, t - self.t_prev)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


class ThumbController:
    """Thumb-direction vehicle controller using MediaPipe Tasks API."""

    def __init__(
        self,
        model_path: str = "hand_landmarker.task",
        target_ip: str = "127.0.0.1",
        target_port: int = 5005,
        camera_idx: int = 0,
        user: str = "default",
        use_yolo: bool = True,
        yolo_model_path: str = None,
        num_hands: int = 1,
    ):
        # Resolve model path flexibly across working directories
        resolved_model_path = model_path
        if not Path(resolved_model_path).exists():
            parent_path = Path(__file__).parent / model_path
            if parent_path.exists():
                resolved_model_path = str(parent_path)
            else:
                root_path = Path(__file__).parent.parent / model_path
                if root_path.exists():
                    resolved_model_path = str(root_path)

        self.model_path = resolved_model_path
        self.client = GestureClient(target_ip=target_ip, target_port=target_port)
        self.camera_idx = camera_idx
        self.user = user
        # Per-user calibration (see calibration.py); defaults until calibrated
        self.profile = CalibrationProfile.load(user) or CalibrationProfile(user=user)
        self.calibration = None  # active CalibrationSession, if any

        # ---- YOLO static-gesture commands (gear / horn / emergency stop) ----
        self.yolo = None
        if use_yolo:
            model = Path(yolo_model_path) if yolo_model_path else default_yolo_model_path()
            try:
                if not model.exists():
                    raise FileNotFoundError(model)
                self.yolo = YoloGestureWorker(model)
                print(f"[YOLO] Loaded {model.name} on {'GPU' if self.yolo.cuda else 'CPU'}")
            except ImportError:
                print("[YOLO] 'ultralytics' not installed in this Python - commands use MediaPipe "
                      "only (emergency stop). Run with the project .venv to enable YOLO.")
            except Exception as err:
                print(f"[YOLO] Disabled ({type(err).__name__}: {err}) - MediaPipe-only stop.")
        self.commands = GestureCommandInterpreter(yolo_enabled=self.yolo is not None)
        self.cmd = None  # latest CommandState
        self._last_t = {}
        self._log_file = None
        self._log = None
        self._snap_id = ""
        self._snap_until = 0.0
        self.target_ip = target_ip
        self.target_port = target_port

        # ---- MediaPipe Tasks API Setup ----
        # Lower confidence thresholds for better detection on laptop cameras
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = HandLandmarkerOptions(
            base_options=base_options,
            # VIDEO mode tracks the hand between frames: steadier landmarks, faster than IMAGE
            running_mode=RunningMode.VIDEO,
            # 1 hand by default: MediaPipe then tracks it frame-to-frame (fast). With 2 it
            # re-runs palm detection every frame looking for the second hand (~2x slower).
            num_hands=num_hands,
            min_hand_detection_confidence=0.4,
            min_hand_presence_confidence=0.4,
            min_tracking_confidence=0.4,
        )
        self.landmarker = HandLandmarker.create_from_options(options)
        self._t0 = time.monotonic()
        self._last_ts_ms = -1

        # ---- Smoothing & Stabilization ----
        # One Euro filters: min_cutoff = smoothing at rest, beta = responsiveness when moving
        self.steer_filter = OneEuroFilter(min_cutoff=1.2, beta=0.8)
        self.throttle_filter = OneEuroFilter(min_cutoff=0.8, beta=0.4)
        self.brake_filter = OneEuroFilter(min_cutoff=1.5, beta=0.8)  # brake reacts faster
        self.stable_frames = 4  # frames needed before the HUD direction label changes

        self.smooth_steer = 0.0
        self.smooth_throttle = 0.0
        self.smooth_brake = 0.0

        self.stable_direction = "NONE"
        self.candidate_direction = "NONE"
        self.direction_count = 0

        # Hand-loss handling: hold last command briefly, then decay to idle
        self.last_seen = 0.0
        self.loss_hold_sec = 0.25
        self.loss_decay_per_sec = 3.0

        # Landmark indices (MediaPipe hand model)
        self.WRIST = 0
        self.THUMB_MCP = 2   # Thumb metacarpophalangeal joint (base)
        self.THUMB_TIP = 4   # Thumb tip
        self.PALM_POINTS = (0, 5, 9, 13, 17)  # wrist + finger bases = palm centre

        # Steering curve shape; ranges and dead zones come from self.profile
        self.steer_expo = 0.35       # 0 = linear, 1 = cubic; finer control near centre

    # ------------------------------------------------------------------
    # Core vision: thumb direction + position
    # ------------------------------------------------------------------

    def detect_thumb(self, frame):
        """Run HandLandmarker on a frame and extract thumb + palm metrics.

        Returns dict with:
          found (bool), dx, dy (thumb vector in PIXELS, aspect-corrected),
          thumb_x, thumb_y, base_x, base_y (normalised 0..1),
          palm_x, palm_y (palm centre, normalised 0..1),
          mp_gesture (finger pattern of the driving hand),
          other_gestures (finger patterns of any other visible hand)
        """
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode needs strictly increasing timestamps
        ts_ms = max(self._last_ts_ms + 1, int((time.monotonic() - self._t0) * 1000))
        self._last_ts_ms = ts_ms
        result = self.landmarker.detect_for_video(mp_image, ts_ms)

        out = {"found": False}
        if not result.hand_landmarks:
            return out

        # Driving hand = the largest (closest to the camera), so a second hand resting
        # in view (or someone behind you) can't take over steering.
        def hand_size(lm):
            return np.hypot((lm[0].x - lm[9].x) * w, (lm[0].y - lm[9].y) * h)

        hands = sorted(result.hand_landmarks, key=hand_size, reverse=True)
        hand = hands[0]
        fingers = finger_states(hand, w, h)
        base = hand[self.THUMB_MCP]
        tip = hand[self.THUMB_TIP]
        palm_x = sum(hand[i].x for i in self.PALM_POINTS) / len(self.PALM_POINTS)
        palm_y = sum(hand[i].y for i in self.PALM_POINTS) / len(self.PALM_POINTS)

        out.update({
            "found": True,
            # Landmarks are normalised separately by width and height, so a 16:9 frame
            # squashes horizontal motion. Convert to pixels before measuring angles.
            "dx": (tip.x - base.x) * w,
            "dy": (tip.y - base.y) * h,
            "thumb_x": tip.x,
            "thumb_y": tip.y,
            "base_x": base.x,
            "base_y": base.y,
            "palm_x": palm_x,
            "palm_y": palm_y,
            "fingers": fingers,
            "mp_gesture": pattern_from_states(fingers["state"]),
            "other_gestures": [pattern_from_states(finger_states(o, w, h)["state"]) for o in hands[1:]],
        })
        return out

    # ------------------------------------------------------------------
    # Control mapping
    # ------------------------------------------------------------------

    def _classify_direction(self, dx, dy):
        """Label the thumb vector LEFT/RIGHT/UP/DOWN (used for HUD + panic only)."""
        if abs(dx) > abs(dy):
            return "RIGHT" if dx > 0 else "LEFT"
        return "UP" if dy < 0 else "DOWN"

    def _stabilize(self, raw_direction):
        """Frame-based stabilization: require N consistent frames to switch."""
        if raw_direction == self.stable_direction:
            self.candidate_direction = raw_direction
            self.direction_count = 0
        else:
            if raw_direction == self.candidate_direction:
                self.direction_count += 1
            else:
                self.candidate_direction = raw_direction
                self.direction_count = 1

            if self.direction_count >= self.stable_frames:
                self.stable_direction = self.candidate_direction
                self.direction_count = 0

        return self.stable_direction

    def thumb_angle_deg(self, dx, dy):
        """Signed tilt of the thumb from vertical-up: 0 = up, -90 = left, +90 = right."""
        return float(np.degrees(np.arctan2(dx, -dy)))

    def steer_from_angle(self, angle_deg):
        """Tilt relative to the user's neutral -> steer, with dead zone + expo curve.

        Left and right use separate ranges, since most people can tilt one way further.
        """
        p = self.profile
        rel = (angle_deg - p.neutral_angle + 180.0) % 360.0 - 180.0
        full = p.steer_right_deg if rel > 0 else p.steer_left_deg
        a = abs(rel)
        if a <= p.steer_dead_deg:
            return 0.0
        # Tilting past full lock (even pointing down) just stays at full lock
        x = min(1.0, (a - p.steer_dead_deg) / max(1.0, full - p.steer_dead_deg))
        x = (1 - self.steer_expo) * x + self.steer_expo * x ** 3
        return float(np.copysign(x, rel))

    def pedals_from_palm(self, palm_y):
        """Palm height -> (throttle, brake). Mutually exclusive by construction."""
        p = self.profile
        half_dz = p.pedal_dead_zone / 2.0
        up = (p.pedal_center - half_dz) - palm_y     # >0 when palm above dead zone
        down = palm_y - (p.pedal_center + half_dz)   # >0 when palm below dead zone
        throttle = max(0.0, min(1.0, up / p.throttle_range))
        brake = max(0.0, min(1.0, down / p.brake_range))
        return throttle, brake

    def map_to_vehicle(self, dx, dy, thumb_x, thumb_y, palm_y):
        """Convert raw hand metrics into (unfiltered) vehicle control channels.

        Returns (steer, throttle, brake, panic, direction, intensity)
        """
        direction = self._stabilize(self._classify_direction(dx, dy))

        # Steering and pedals come from different features, so they don't fight
        angle = self.thumb_angle_deg(dx, dy)
        steer = self.steer_from_angle(angle)
        throttle, brake = self.pedals_from_palm(palm_y)

        # Intensity = how hard the dominant channel is being pushed (HUD only)
        intensity = 100.0 * max(abs(steer), throttle, brake)

        # Panic stop: thumb pointing down AND palm at the very bottom
        panic = direction == "DOWN" and brake >= 1.0

        return steer, throttle, brake, panic, direction, intensity

    # ------------------------------------------------------------------
    # HUD overlay
    # ------------------------------------------------------------------

    def _draw_hud(self, frame, steer, throttle, brake, panic, direction, intensity, fps):
        h, w, _ = frame.shape

        # Top bar
        cv2.rectangle(frame, (0, 0), (w, 90), (18, 22, 30), -1)
        cv2.line(frame, (0, 90), (w, 90), (50, 70, 95), 2)

        # Title + connection
        cv2.putText(frame, "MediaPipe Thumb Controller -> Simulator",
                    (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 215, 255), 1)
        cv2.putText(frame, f"UDP {self.target_ip}:{self.target_port}  |  FPS {fps:.0f}",
                    (15, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 180, 195), 1)
        calib_txt = (f"User: {self.profile.user} (calibrated)" if self.profile.calibrated
                     else f"User: {self.profile.user} (NOT calibrated)")
        calib_col = (0, 255, 140) if self.profile.calibrated else (0, 165, 255)
        cv2.putText(frame, calib_txt + "  |  C = calibrate", (w - 420, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, calib_col, 1)

        # Direction + intensity
        dir_col = (0, 255, 140)
        cv2.putText(frame, f"DIR: {direction}  INT: {intensity:.0f}%",
                    (15, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.6, dir_col, 2)

        # Panic banner
        if panic:
            cv2.rectangle(frame, (0, 95), (w, 140), (0, 0, 200), -1)
            cv2.putText(frame, "!! PANIC STOP !!", (w // 2 - 150, 127),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

    def _draw_calibration(self, frame, status, t):
        """Full-screen guidance overlay for the calibration routine."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 170), (18, 22, 30), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        cv2.putText(frame, f"CALIBRATION  -  {status['title']}", (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 215, 255), 2)
        cv2.putText(frame, status["instruction"], (20, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (235, 235, 235), 2)

        if status["retry"]:
            msg, col = "Hand not seen clearly - repeating this step", (0, 140, 255)
        elif not status["recording"]:
            msg, col = f"Get ready... {status['countdown']:.1f}s", (0, 215, 255)
        elif not t["found"]:
            msg, col = "Show your hand to the camera!", (0, 0, 255)
        else:
            msg, col = "Recording - hold it", (0, 255, 140)
        cv2.putText(frame, msg, (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2)
        cv2.putText(frame, "S = skip calibration", (w - 260, 125),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (170, 180, 195), 1)

        # Progress bar for the current step
        cv2.rectangle(frame, (20, 145), (w - 20, 160), (40, 48, 60), -1)
        cv2.rectangle(frame, (20, 145), (20 + int((w - 40) * status["progress"]), 160),
                      (0, 255, 140), -1)

        if t["found"]:
            tx, ty = int(t["thumb_x"] * w), int(t["thumb_y"] * h)
            bx, by = int(t["base_x"] * w), int(t["base_y"] * h)
            px, py = int(t["palm_x"] * w), int(t["palm_y"] * h)
            cv2.line(frame, (bx, by), (tx, ty), (0, 215, 255), 4)
            cv2.circle(frame, (tx, ty), 12, (0, 215, 255), -1)
            cv2.drawMarker(frame, (px, py), (0, 215, 255), cv2.MARKER_CROSS, 22, 2)

    def _draw_zones(self, frame, w, h, steer=0.0, throttle=0.0, brake=0.0):
        """Draw visual guides for throttle/brake zones and steering range."""
        # Vertical zones (left side)
        # Zones follow the user's calibrated pedal centre and dead zone
        center_y = int(h * self.profile.pedal_center)
        dead_zone = int(h * self.profile.pedal_dead_zone / 2)
        
        # Throttle zone (top) - green tint
        cv2.rectangle(frame, (10, 100), (30, center_y - dead_zone), (0, 80, 0), -1)
        cv2.putText(frame, "THROTTLE", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 100), 1)
        
        # Coasting zone (center) - gray
        cv2.rectangle(frame, (10, center_y - dead_zone), (30, center_y + dead_zone), (60, 60, 60), -1)
        cv2.putText(frame, "COAST", (10, center_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)
        
        # Brake zone (bottom) - red tint
        cv2.rectangle(frame, (10, center_y + dead_zone), (30, h - 100), (80, 0, 0), -1)
        cv2.putText(frame, "BRAKE", (10, h - 105), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 80, 80), 1)
        
        # Horizontal steering indicator (bottom center)
        cx = w // 2
        cv2.line(frame, (cx - 200, h - 50), (cx + 200, h - 50), (80, 80, 80), 2)
        cv2.line(frame, (cx, h - 55), (cx, h - 45), (255, 255, 255), 2)
        cv2.putText(frame, "STEER LEFT", (cx - 190, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)
        cv2.putText(frame, "STEER RIGHT", (cx + 100, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)

        # Telemetry gauges (bottom)
        gy = h - 110
        cv2.rectangle(frame, (15, gy), (300, h - 12), (18, 22, 30), -1)
        cv2.rectangle(frame, (15, gy), (300, h - 12), (50, 70, 95), 1)

        # Steering gauge
        cx = 215
        cv2.putText(frame, f"STEER {steer:+.2f}", (25, gy + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 210, 0), 1)
        cv2.rectangle(frame, (130, gy + 12), (300, gy + 26), (40, 48, 60), -1)
        cv2.line(frame, (cx, gy + 12), (cx, gy + 26), (255, 255, 255), 1)
        off = int(steer * 85)
        cv2.rectangle(frame, (cx, gy + 12), (cx + off, gy + 26), (255, 210, 0), -1)

        # Throttle bar
        cv2.putText(frame, f"THR {throttle:.2f}", (25, gy + 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 220, 120), 1)
        cv2.rectangle(frame, (130, gy + 40), (300, gy + 54), (40, 48, 60), -1)
        cv2.rectangle(frame, (130, gy + 40), (130 + int(170 * throttle), gy + 54), (60, 220, 120), -1)

        # Brake bar
        cv2.putText(frame, f"BRK {brake:.2f}", (25, gy + 78),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 90, 255), 1)
        cv2.rectangle(frame, (130, gy + 68), (300, gy + 82), (40, 48, 60), -1)
        cv2.rectangle(frame, (130, gy + 68), (130 + int(170 * brake), gy + 82), (90, 90, 255), -1)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def start_calibration(self):
        print(f"[Calibration] Starting calibration for user '{self.user}'...")
        self.calibration = CalibrationSession(self.user)

    def _finish_calibration(self):
        profile = self.calibration.profile
        self.calibration = None
        self.profile = profile
        path = profile.save()
        print(f"[Calibration] Saved {path}")
        print(f"[Calibration] {profile.summary()}")
        for note in profile.notes:
            print(f"[Calibration] Note: {note}")
        # Start driving from a clean state with the new mapping
        for f in (self.steer_filter, self.throttle_filter, self.brake_filter):
            f.reset()
        self.smooth_steer = self.smooth_throttle = self.smooth_brake = 0.0
        self.commands.reset_votes()

    def _draw_hand_command(self, frame, t):
        """Hand visible but driving paused: mark the palm and show the finger pattern."""
        h, w = frame.shape[:2]
        px, py = int(t["palm_x"] * w), int(t["palm_y"] * h)
        cv2.circle(frame, (px, py), 40, (0, 165, 255), 3)
        cv2.putText(frame, f"MP: {t['mp_gesture']}", (px + 48, py),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

    def _draw_yolo(self, frame, cmd):
        """YOLO box/label, gear and horn state on the camera view."""
        h, w = frame.shape[:2]
        res = self.yolo.latest() if self.yolo is not None else None
        if res and res["box"] is not None and cmd.yolo_label not in ("-", "none"):
            x1, y1, x2, y2 = (int(v) for v in (res["box"][0] * w, res["box"][1] * h,
                                               res["box"][2] * w, res["box"][3] * h))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 170, 0), 2)
            cv2.putText(frame, f"YOLO {cmd.yolo_label} {cmd.yolo_conf:.2f}", (x1, max(110, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 170, 0), 2)

        # Command panel (top right, under the header bar)
        x0, y0 = w - 330, 100
        cv2.rectangle(frame, (x0, y0), (w - 15, y0 + 162), (18, 22, 30), -1)
        cv2.rectangle(frame, (x0, y0), (w - 15, y0 + 162), (50, 70, 95), 1)
        if cmd.gear < 0:
            gear_txt, gear_col = "R  (reverse)", (0, 200, 255)
        else:
            gear_txt, gear_col = "D  (forward)", (0, 255, 140)
        cv2.putText(frame, f"GEAR  {gear_txt}", (x0 + 12, y0 + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, gear_col, 2)
        horn_col = (0, 255, 255) if cmd.horn else (110, 120, 135)
        cv2.putText(frame, "HORN  " + ("ON" if cmd.horn else "off"), (x0 + 12, y0 + 56),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, horn_col, 2)
        if self.yolo is None:
            yolo_txt = "YOLO  off (MP stop only)"
        elif self.yolo.failed:
            yolo_txt = "YOLO  failed (MP stop only)"
        elif not self.yolo.ready:
            yolo_txt = "YOLO  loading..."
        else:
            ms = res["ms"] if res else 0.0
            yolo_txt = f"YOLO  {cmd.yolo_label} {cmd.yolo_conf:.2f} ({ms:.0f}ms)"
        cv2.putText(frame, yolo_txt, (x0 + 12, y0 + 84),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 170, 0), 1)
        # Diagnostics: what MediaPipe sees, and how far each command's vote has got.
        # A command needs YOLO and MediaPipe to agree, so both lines must show it.
        mp_txt = f"MP    {self._last_t.get('mp_gesture', '-')}" if self._last_t.get("found") else "MP    no hand"
        if self._last_t.get("found"):
            st = self._last_t["fingers"]["state"]
            mp_txt += "  [" + " ".join(f"{k[0].upper()}:{v}" for k, v in st.items()) + "]"
        cv2.putText(frame, mp_txt, (x0 + 12, y0 + 106), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
        cv2.putText(frame, f"votes  gear {cmd.gear_votes}/5  horn {cmd.horn_votes}/5  stop {cmd.stop_votes}/3",
                    (x0 + 12, y0 + 128), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(frame, "peace=gear  call=horn  palm=STOP", (x0 + 12, y0 + 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (170, 180, 195), 1)

    def _snapshot(self, frame, send_to_sim=True):
        """P key: save the camera view, and ask the simulator to save its view with the
        same id, giving a matched camera + simulator pair (report_screenshots/)."""
        snap_id = time.strftime("%Y%m%d_%H%M%S")
        out_dir = Path(__file__).resolve().parent.parent / "report_screenshots"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{snap_id}_camera.png"
            cv2.imwrite(str(path), frame)
            print(f"[Snapshot] Camera view saved: {path}")
        except OSError as err:
            print(f"[Snapshot] Failed: {err}")
            return
        if send_to_sim:
            # Repeat the id for half a second so a dropped UDP packet can't lose it
            self._snap_id, self._snap_until = snap_id, time.monotonic() + 0.5

    def _open_log(self):
        """Per-session CSV of every frame's gesture decisions (for debugging / the report)."""
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            path = log_dir / f"gesture_session_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            self._log_file = open(path, "w", newline="", encoding="utf-8")
            self._log = csv.writer(self._log_file)
            self._log.writerow(["t", "hand", "mp_pattern", "r_index", "r_middle", "r_ring", "r_pinky",
                                "yolo_label", "yolo_conf", "yolo_age", "source", "fused",
                                "stop_votes", "gear_votes", "horn_votes", "gear", "horn", "panic",
                                "suppress_driving", "steer", "throttle", "brake"])
            print(f"[Log] Writing gesture log to {path}")
        except OSError as err:
            print(f"[Log] Could not open log ({err}) - continuing without it.")
            self._log = None

    def _log_frame(self, now, t, cmd):
        if self._log is None:
            return
        r = t["fingers"]["ratios"] if t.get("found") else {}
        self._log.writerow([
            f"{now:.3f}", int(bool(t.get("found"))), t.get("mp_gesture", ""),
            *(f"{r[k]:.2f}" if k in r else "" for k in ("index", "middle", "ring", "pinky")),
            cmd.yolo_label, f"{cmd.yolo_conf:.2f}", f"{cmd.yolo_age:.3f}", cmd.source, cmd.fused,
            cmd.stop_votes, cmd.gear_votes, cmd.horn_votes, cmd.gear, int(cmd.horn), int(cmd.panic),
            int(cmd.suppress_driving), f"{self.smooth_steer:.3f}", f"{self.smooth_throttle:.3f}",
            f"{self.smooth_brake:.3f}",
        ])

    def run(self, should_stop=None, calibrate=False):
        """Camera loop. `should_stop` is polled each frame (e.g. simulator window closed)."""
        cap = cv2.VideoCapture(self.camera_idx)
        if not cap.isOpened():
            print(f"[Error] Cannot open webcam index {self.camera_idx}")
            return
        # Higher resolution for laptop camera - capture wider field of view
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        # Try to set higher FPS
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("=" * 68)
        print("  MEDIAPIPE THUMB CONTROLLER (Part A) -> SIMULATOR (Part B)")
        print(f"  Streaming UDP to {self.target_ip}:{self.target_port}")
        print("  Controls: thumb direction = steer | thumb height = pedals")
        print("  Keys (camera window): Q/ESC = quit | C = recalibrate | S = skip calibration | P = screenshot")
        print("=" * 68)

        # Create resizable window
        cv2.namedWindow("Thumb Controller (Part A)", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Thumb Controller (Part A)", 1280, 720)

        prev_time = time.time()
        fps_est = 30.0
        if self.yolo is not None:
            self.yolo.start()
        self._open_log()
        if calibrate or not self.profile.calibrated:
            self.start_calibration()
        else:
            print(f"[Calibration] Loaded profile '{self.user}': {self.profile.summary()}")

        try:
            while True:
                if should_stop and should_stop():
                    print("[ThumbController] Simulator closed - shutting down camera.")
                    break

                ok, frame = cap.read()
                if not ok:
                    print("[Warning] empty frame")
                    continue

                frame = cv2.flip(frame, 1)
                if self.yolo is not None:
                    self.yolo.submit(frame.copy())  # copy: we draw on `frame` below
                t = self.detect_thumb(frame)
                self._last_t = t
                now = time.monotonic()
                h, w, _ = frame.shape

                if self.calibration is not None:
                    # Calibration mode: record poses, hold the car still with the brake
                    found = t["found"]
                    self.calibration.feed(
                        now,
                        self.thumb_angle_deg(t["dx"], t["dy"]) if found else None,
                        t["palm_y"] if found else None,
                    )
                    self.client.send(steering_angle=0.0, throttle=0.0, brake=1.0)
                    if self.calibration.done:
                        self._finish_calibration()
                    else:
                        self._draw_calibration(frame, self.calibration.status(now), t)
                        cv2.imshow("Thumb Controller (Part A)", frame)
                        key = cv2.waitKey(1) & 0xFF
                        if key in (ord("q"), 27):
                            break
                        if key == ord("p"):
                            self._snapshot(frame, send_to_sim=False)
                        if key == ord("s"):
                            print("[Calibration] Skipped - keeping current profile.")
                            self.calibration = None
                        continue

                yolo_alive = self.yolo is not None and self.yolo.failed is None
                cmd = self.commands.update(
                    now,
                    t["mp_gesture"] if t["found"] else None,
                    self.yolo.latest() if yolo_alive else None,
                    yolo_alive,
                    other_patterns=t.get("other_gestures", ()),
                )
                self.cmd = cmd
                self._log_frame(now, t, cmd)

                if t["found"] and not cmd.suppress_driving:
                    self.last_seen = now
                    steer, throttle, brake, panic, direction, intensity = self.map_to_vehicle(
                        t["dx"], t["dy"], t["thumb_x"], t["thumb_y"], t["palm_y"]
                    )

                    # Adaptive smoothing per channel; panic bypasses filtering entirely
                    self.smooth_steer = self.steer_filter(steer, now)
                    self.smooth_throttle = 0.0 if panic else self.throttle_filter(throttle, now)
                    self.smooth_brake = 1.0 if panic else self.brake_filter(brake, now)

                    # Draw thumb line + palm centre
                    bx, by = int(t["base_x"] * w), int(t["base_y"] * h)
                    tx, ty = int(t["thumb_x"] * w), int(t["thumb_y"] * h)
                    px, py = int(t["palm_x"] * w), int(t["palm_y"] * h)
                    line_col = (0, 0, 255) if panic else (0, 255, 140)
                    cv2.line(frame, (bx, by), (tx, ty), line_col, 4)
                    cv2.circle(frame, (tx, ty), 12, line_col, -1)
                    cv2.circle(frame, (bx, by), 8, (255, 255, 255), 2)
                    cv2.drawMarker(frame, (px, py), (0, 215, 255), cv2.MARKER_CROSS, 22, 2)
                    cv2.putText(frame, f"{self.thumb_angle_deg(t['dx'], t['dy']):+.0f} deg",
                                (tx + 16, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, line_col, 2)
                else:
                    # Hand lost, or hand making a command gesture: driving input paused
                    panic, intensity = False, 0.0
                    self.stable_direction = "NONE"
                    self.candidate_direction = "NONE"
                    self.direction_count = 0
                    direction = cmd.fused.upper() if t["found"] else "NONE"
                    if cmd.horn:
                        # Honking while driving: keep the current steering/throttle
                        self.last_seen = now
                    elif now - self.last_seen > self.loss_hold_sec:
                        # Hand gone: ease everything back to idle instead of snapping
                        decay = self.loss_decay_per_sec / max(1.0, fps_est)
                        self.smooth_steer = float(np.sign(self.smooth_steer)) * max(0.0, abs(self.smooth_steer) - decay)
                        self.smooth_throttle = max(0.0, self.smooth_throttle - decay)
                        self.smooth_brake = max(0.0, self.smooth_brake - decay)
                    # Pin filters to the held values so driving resumes without a jump
                    for f, v in ((self.steer_filter, self.smooth_steer),
                                 (self.throttle_filter, self.smooth_throttle),
                                 (self.brake_filter, self.smooth_brake)):
                        f.hold(v, now)

                    if t["found"]:
                        self._draw_hand_command(frame, t)

                # YOLO emergency stop (open palm) overrides everything
                if cmd.panic:
                    panic = True
                    self.smooth_throttle, self.smooth_brake = 0.0, 1.0
                    for f, v in ((self.throttle_filter, 0.0), (self.brake_filter, 1.0)):
                        f.hold(v, now)
                self._draw_yolo(frame, cmd)

                self._draw_zones(frame, w, h, self.smooth_steer, self.smooth_throttle, self.smooth_brake)

                # Send UDP telemetry
                self.client.send(
                    steering_angle=self.smooth_steer,
                    throttle=self.smooth_throttle,
                    brake=self.smooth_brake,
                    panic_stop=panic,
                    gear=cmd.gear,
                    horn=cmd.horn,
                    gesture=cmd.yolo_label,
                    snap=self._snap_id if time.monotonic() < self._snap_until else "",
                )

                # HUD + display
                fps = 1.0 / max(1e-3, time.time() - prev_time)
                prev_time = time.time()
                fps_est = 0.9 * fps_est + 0.1 * fps
                self._draw_hud(frame, self.smooth_steer, self.smooth_throttle,
                               self.smooth_brake, panic, direction, intensity, fps)
                cv2.imshow("Thumb Controller (Part A)", frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("c"):
                    self.start_calibration()
                if key == ord("p"):
                    self._snapshot(frame)
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.client.close()
            self.landmarker.close()
            if self.yolo is not None:
                self.yolo.stop()
            if self._log_file is not None:
                self._log_file.close()
            print("[ThumbController] Exited cleanly.")


def launch_simulator(port: int, width: int, height: int) -> subprocess.Popen:
    """Start the Pygame simulator (Part B) as a child process listening on `port`."""
    sim_dir = Path(__file__).resolve().parent
    cmd = [sys.executable, str(sim_dir / "main.py"),
           "--port", str(port), "--width", str(width), "--height", str(height)]
    print(f"[Launcher] Starting simulator: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=str(sim_dir))


def main():
    parser = argparse.ArgumentParser(description="MediaPipe Thumb Controller -> Vehicle Simulator")
    parser.add_argument("--model", type=str, default="hand_landmarker.task", help="Path to hand_landmarker.task")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Simulator UDP IP")
    parser.add_argument("--port", type=int, default=5005, help="Simulator UDP port")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index")
    parser.add_argument("--user", type=str, default="default",
                        help="Calibration profile name (each user calibrates once)")
    parser.add_argument("--calibrate", action="store_true",
                        help="Force calibration even if a saved profile exists")
    parser.add_argument("--two-hands", action="store_true",
                        help="Track 2 hands: steer with the closest, gesture with either (slower)")
    parser.add_argument("--no-yolo", action="store_true",
                        help="Disable YOLO gesture commands (gear/horn); open-palm stop still works")
    parser.add_argument("--yolo-model", type=str, default=None,
                        help="Path to the YOLO gesture model (default: models/gesture_yolo11n_best.pt)")
    parser.add_argument("--no-simulator", action="store_true",
                        help="Do not auto-launch the simulator (use when it runs elsewhere)")
    parser.add_argument("--width", type=int, default=1280, help="Simulator window width")
    parser.add_argument("--height", type=int, default=720, help="Simulator window height")
    args = parser.parse_args()

    # YOLO needs ultralytics + torch, which live in the project .venv, not simulator/venv.
    # If we were started with a Python that lacks them, re-run ourselves with the .venv
    # so gear/horn always work no matter which python.exe was typed.
    if not args.no_yolo and importlib.util.find_spec("ultralytics") is None:
        project_py = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
        if project_py.exists() and Path(sys.executable).resolve() != project_py.resolve():
            print(f"[Launcher] This Python has no YOLO support - restarting with {project_py}")
            sys.exit(subprocess.call([str(project_py), str(Path(__file__).resolve()), *sys.argv[1:]]))
        print("[Launcher] WARNING: YOLO unavailable - gear and horn gestures are DISABLED "
              "(open-palm stop still works). Install ultralytics or use the project .venv.")

    # Closed loop: camera (Part A) and simulator (Part B) run and exit together.
    sim = None
    if not args.no_simulator:
        sim = launch_simulator(args.port, args.width, args.height)
        time.sleep(1.5)  # let the simulator bind its UDP port before we stream
        if sim.poll() is not None:
            print("[Launcher] Simulator failed to start - see errors above.")
            sys.exit(1)

    try:
        controller = ThumbController(
            model_path=args.model,
            target_ip=args.ip,
            target_port=args.port,
            camera_idx=args.camera,
            user=args.user,
            use_yolo=not args.no_yolo,
            yolo_model_path=args.yolo_model,
            num_hands=2 if args.two_hands else 1,
        )
        controller.run(should_stop=(lambda: sim.poll() is not None) if sim else None,
                       calibrate=args.calibrate)
    finally:
        if sim and sim.poll() is None:
            print("[Launcher] Closing simulator...")
            sim.terminate()
            try:
                sim.wait(timeout=3)
            except subprocess.TimeoutExpired:
                sim.kill()


if __name__ == "__main__":
    main()
