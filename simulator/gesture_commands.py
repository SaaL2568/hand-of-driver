"""YOLO static-gesture commands fused with MediaPipe hand landmarks.

Two tiers:
  * MediaPipe (every frame)  -> continuous driving: steering + pedals.
  * YOLO11 (background thread) -> discrete commands:
        palm / stop -> EMERGENCY STOP (held)
        peace       -> toggle GEAR forward <-> reverse (one shot)
        call        -> HORN (held)

A command only fires when YOLO's label AND MediaPipe's finger pattern agree, and
only after it wins a short majority vote over recent frames. The driving pose
(thumb up, fingers folded) can never match a command pattern, so steering can't
trigger commands. The emergency stop is fail-safe: if YOLO is unavailable or has
no fresh result, MediaPipe's open-palm pattern alone is enough.
"""
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# YOLO class -> command it maps to (classes not listed are ignored)
YOLO_TO_COMMAND = {"palm": "stop", "stop": "stop", "peace": "gear", "call": "horn"}
# MediaPipe finger pattern -> command it is compatible with
PATTERN_TO_COMMAND = {"palm": "stop", "peace": "gear", "call": "horn"}

# Landmark indices (MCP, PIP, TIP) for index, middle, ring, pinky
FINGERS = {"index": (5, 6, 8), "middle": (9, 10, 12), "ring": (13, 14, 16), "pinky": (17, 18, 20)}


def finger_states(hand, w: int, h: int) -> dict:
    """Per-finger state from MediaPipe landmarks: "ext", "fold" or "?" (in between).

    Extended = tip clearly further from the wrist than the PIP joint. Rotation
    invariant; aspect corrected. Also returns the raw ratios for diagnostics.
    """
    def pt(i):
        return np.array([hand[i].x * w, hand[i].y * h])

    wrist = pt(0)
    state, ratios = {}, {}
    for name, (_, pip, tip) in FINGERS.items():
        ratio = np.linalg.norm(pt(tip) - wrist) / max(1e-6, np.linalg.norm(pt(pip) - wrist))
        ratios[name] = float(ratio)
        state[name] = "ext" if ratio > 1.12 else ("fold" if ratio < 1.0 else "?")
    return {"state": state, "ratios": ratios}


def pattern_from_states(state: dict) -> str:
    """Map finger states to "palm", "peace", "call", "fist" (driving pose) or "other".

    Command shapes only require the "other" fingers to be NOT extended (folded or
    loosely curled), so a relaxed peace/call still counts. This can't misfire while
    driving: the driving pose has no extended fingers, and every command needs at
    least one clearly extended finger.
    """
    ext = {n for n, st in state.items() if st == "ext"}
    fold = {n for n, st in state.items() if st == "fold"}
    if len(ext) == 4:
        return "palm"
    if ext == {"index", "middle"}:
        return "peace"
    if ext == {"pinky"}:
        return "call"
    if len(fold) == 4:
        return "fist"
    return "other"


def finger_pattern(hand, w: int, h: int) -> str:
    """Classify the hand shape from MediaPipe landmarks (see pattern_from_states)."""
    return pattern_from_states(finger_states(hand, w, h)["state"])


def default_yolo_model_path() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "models" / "gesture_yolo11n_best.pt",
                 here.parent / "runs" / "detect" / "runs" / "gestureModelV1" / "weights" / "best.pt"):
        if cand.exists():
            return cand
    return here.parent / "models" / "gesture_yolo11n_best.pt"


class YoloGestureWorker:
    """Runs the YOLO11 gesture model on the newest camera frame in a background thread,
    so detection speed never slows down the MediaPipe driving loop."""

    def __init__(self, model_path: Path, conf: float = 0.5, imgsz: int = 640):
        from ultralytics import YOLO  # ImportError -> caller disables YOLO
        import torch

        self.cuda = torch.cuda.is_available()
        self.device = 0 if self.cuda else "cpu"
        if not self.cuda:
            torch.set_num_threads(2)  # leave CPU cores for MediaPipe
        self.model = YOLO(str(model_path))
        self.names = self.model.names
        self.conf = conf
        self.imgsz = imgsz

        self._lock = threading.Lock()
        self._new_frame = threading.Event()
        self._frame = None
        self._result = None
        self._running = False
        self._thread = None
        self.ready = False
        self.failed: Optional[str] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="YoloGestureWorker")
        self._thread.start()

    def stop(self):
        self._running = False
        self._new_frame.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def submit(self, frame):
        """Hand over the newest frame (caller must pass a copy it won't draw on)."""
        with self._lock:
            self._frame = frame
        self._new_frame.set()

    def latest(self) -> Optional[dict]:
        with self._lock:
            return self._result

    def _predict(self, frame):
        return self.model.predict(frame, imgsz=self.imgsz, conf=self.conf, device=self.device,
                                  verbose=False)[0]

    def _loop(self):
        try:
            self._predict(np.zeros((480, 640, 3), np.uint8))  # warm-up (CUDA init, etc.)
            self.ready = True
            while self._running:
                if not self._new_frame.wait(timeout=0.1):
                    continue
                self._new_frame.clear()
                with self._lock:
                    frame, self._frame = self._frame, None
                if frame is None:
                    continue
                t0 = time.monotonic()
                res = self._predict(frame)
                label, conf, box = "none", 0.0, None
                if res.boxes is not None and len(res.boxes):
                    i = int(res.boxes.conf.argmax())
                    label = self.names[int(res.boxes.cls[i])]
                    conf = float(res.boxes.conf[i])
                    box = [float(v) for v in res.boxes.xyxyn[i].tolist()]
                with self._lock:
                    self._result = {"label": label, "conf": conf, "box": box,
                                    "ts": time.monotonic(), "ms": (time.monotonic() - t0) * 1000}
        except Exception as err:  # never take the driving loop down with us
            self.failed = f"{type(err).__name__}: {err}"
            print(f"[YOLO] Worker stopped - {self.failed}. Falling back to MediaPipe-only commands.")


@dataclass
class CommandState:
    panic: bool = False
    horn: bool = False
    gear: int = 1                   # 1 = forward (D), -1 = reverse (R)
    suppress_driving: bool = False  # hand is making a command shape -> pause steering/pedals
    fused: str = "none"             # command agreed this frame (before voting)
    yolo_label: str = "-"
    yolo_conf: float = 0.0
    yolo_age: float = -1.0          # seconds since the YOLO result used (-1 = none)
    source: str = "YOLO+MP"
    stop_votes: int = 0             # diagnostics: current vote counts
    gear_votes: int = 0
    horn_votes: int = 0


class GestureCommandInterpreter:
    """Fuses YOLO labels with MediaPipe finger patterns and turns them into commands."""

    def __init__(self, yolo_enabled: bool, fresh_sec: float = 0.35, min_conf: float = 0.55):
        self.yolo_enabled = yolo_enabled
        self.fresh_sec = fresh_sec
        self.min_conf = min_conf
        self.stop_votes = deque(maxlen=4)    # emergency stop: 3 of last 4 frames (fast)
        self.cmd_votes = deque(maxlen=7)     # gear / horn: 5 of last 7 frames (robust)
        self.gear = 1
        self.gear_armed = True
        self.last_gear_change = -1e9
        self.gear_cooldown = 1.0

    def reset_votes(self):
        self.stop_votes.clear()
        self.cmd_votes.clear()

    def update(self, now: float, mp_pattern: Optional[str], yolo: Optional[dict],
               yolo_alive: bool, other_patterns=()) -> CommandState:
        """mp_pattern = driving hand's finger pattern; other_patterns = any other visible hand."""
        st = CommandState(gear=self.gear)
        mp_cmd = PATTERN_TO_COMMAND.get(mp_pattern) if mp_pattern else None
        # Commands may come from either hand (e.g. steer with one, honk with the other)
        any_cmds = {PATTERN_TO_COMMAND.get(p) for p in (mp_pattern, *other_patterns) if p}
        any_cmds.discard(None)

        fresh = (yolo_alive and yolo is not None and now - yolo["ts"] <= self.fresh_sec)
        if yolo is not None:
            st.yolo_age = now - yolo["ts"]
        if yolo is not None and fresh:
            st.yolo_label, st.yolo_conf = yolo["label"], yolo["conf"]
        yolo_cmd = None
        if fresh and yolo["conf"] >= self.min_conf:
            yolo_cmd = YOLO_TO_COMMAND.get(yolo["label"])

        # --- Fusion: both models must agree ---
        if fresh:
            fused = yolo_cmd if (yolo_cmd is not None and yolo_cmd in any_cmds) else None
            st.source = "YOLO+MP"
        else:
            # No usable YOLO result: only the safety-critical stop falls back to MediaPipe,
            # and only from the driving hand (a relaxed hand at your side can look open)
            fused = "stop" if mp_cmd == "stop" else None
            st.source = "MP only" if not yolo_alive else "MP (YOLO busy)"
        st.fused = fused or "none"

        # --- Temporal voting ---
        self.stop_votes.append(fused == "stop")
        self.cmd_votes.append(fused)
        st.panic = sum(self.stop_votes) >= 3
        horn_votes = sum(1 for v in self.cmd_votes if v == "horn")
        gear_votes = sum(1 for v in self.cmd_votes if v == "gear")
        st.horn = horn_votes >= 5 and not st.panic
        gear_confirmed = gear_votes >= 5 and not st.panic
        st.stop_votes, st.gear_votes, st.horn_votes = sum(self.stop_votes), gear_votes, horn_votes

        # Gear is one-shot: toggle once per gesture, re-arm after the hand leaves the pose
        if gear_confirmed and self.gear_armed and now - self.last_gear_change >= self.gear_cooldown:
            self.gear = -self.gear
            self.gear_armed = False
            self.last_gear_change = now
            print(f"[Gesture] Gear -> {'R' if self.gear < 0 else 'D'}")
        elif gear_votes == 0:
            self.gear_armed = True
        st.gear = self.gear

        # Pause driving as soon as the DRIVING hand takes a command shape (MediaPipe is
        # per-frame, so this reacts before the vote confirms), or during an emergency stop.
        # A command made with the other hand leaves driving untouched.
        st.suppress_driving = mp_cmd is not None or st.panic
        return st
