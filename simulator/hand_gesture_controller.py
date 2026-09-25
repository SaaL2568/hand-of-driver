"""Hand Gesture Recognition Controller (Part A) using OpenCV & MediaPipe.

Translates real-time webcam hand gestures into UDP vehicle telemetry packets
to control the Pygame Simulator (Part B).

Controls / Gesture Mapping:
---------------------------
[Dual-Hand Mode] (Virtual Steering Wheel):
  - Steering     : Tilt both hands up/down like holding a physical steering wheel (-1.0 to +1.0)
  - Throttle     : Right hand open palm / fingers extended (0.0 to 1.0)
  - Brake / Stop : Right hand closed fist (Spacebar stop equivalent)
  - Panic Stop   : Both hands closed fists or crossed hands

[Single-Hand Mode]:
  - Steering     : Tilt hand left or right (-1.0 to +1.0)
  - Throttle     : Open palm (5 fingers extended)
  - Brake / Stop : Closed fist (0 fingers extended)
  - Reverse      : 2 fingers pointing (Index + Middle)
  - Panic Stop   : Splayed hand pushed close to camera
"""
import argparse
import math
import time
import cv2
import numpy as np
import mediapipe as mp

from gesture_client import GestureClient


class HandGestureController:
    def __init__(self, target_ip: str = "127.0.0.1", target_port: int = 5005, camera_idx: int = 0):
        self.target_ip = target_ip
        self.target_port = target_port
        self.client = GestureClient(target_ip=target_ip, target_port=target_port)
        self.camera_idx = camera_idx

        # MediaPipe Hands Setup
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.65,
            min_tracking_confidence=0.65
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles

        # Smoothing & State Filters
        self.smooth_steer = 0.0
        self.smooth_throttle = 0.0
        self.smooth_brake = 0.0
        self.steer_smoothing_alpha = 0.35   # higher = faster response, lower = smoother

        # Parameters
        self.max_wheel_tilt_deg = 20.0      # degrees tilt for 100% steering lock

    def count_extended_fingers(self, hand_landmarks, is_right_hand: bool = True) -> int:
        """Counts how many fingers are extended (0 to 5)."""
        lm = hand_landmarks.landmark
        extended = 0

        # Thumb: compare tip (4) to IP joint (3) horizontally
        if is_right_hand:
            if lm[4].x < lm[3].x:  # Thumb extended to left for right hand in selfie view
                extended += 1
        else:
            if lm[4].x > lm[3].x:
                extended += 1

        # 4 Fingers: Index(8), Middle(12), Ring(16), Pinky(20)
        finger_tips = [8, 12, 16, 20]
        finger_pips = [6, 10, 14, 18]

        for tip, pip in zip(finger_tips, finger_pips):
            # If tip is higher (lower Y in image coords) than PIP joint
            if lm[tip].y < lm[pip].y:
                extended += 1

        return extended

    def process_two_hands(self, hands_data, img_w: int, img_h: int):
        """
        Calculates steering from tilt angle between two hands (Virtual Steering Wheel),
        and throttle/brake from right hand gestures.
        """
        # Sort hands left-to-right on screen
        sorted_hands = sorted(hands_data, key=lambda h: h["wrist_px"][0])
        left_hand = sorted_hands[0]   # hand on screen left
        right_hand = sorted_hands[1]  # hand on screen right

        # 1. Virtual Steering Wheel Angle
        p1 = left_hand["wrist_px"]
        p2 = right_hand["wrist_px"]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        # Angle in degrees (0 = level horizontal)
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        # Normalize steering to [-1.0, 1.0]
        raw_steer = angle_deg / self.max_wheel_tilt_deg
        raw_steer = max(-1.0, min(1.0, raw_steer))

        # 2. Throttle & Brake from Finger States
        r_fingers = right_hand["extended_count"]
        l_fingers = left_hand["extended_count"]

        # Emergency Panic Stop: Both hands closed into fists
        if r_fingers == 0 and l_fingers == 0:
            return raw_steer, 0.0, 1.0, True, "PANIC STOP (BOTH FISTS)"

        # Right Hand controls forward drive
        if r_fingers >= 3:
            # Open palm -> Throttle (scale 3-5 fingers to 60%-100% gas)
            raw_throttle = (r_fingers / 5.0)
            raw_brake = 0.0
            panic = False
            mode_desc = f"DRIVING (Gas {int(raw_throttle*100)}%)"
        elif r_fingers <= 1:
            # Closed fist -> Brake / Stop
            raw_throttle = 0.0
            raw_brake = 1.0
            panic = False
            mode_desc = "BRAKING / STOP"
        else:
            # 2 fingers -> Coasting
            raw_throttle = 0.0
            raw_brake = 0.0
            panic = False
            mode_desc = "COASTING"

        return raw_steer, raw_throttle, raw_brake, panic, mode_desc

    def process_single_hand(self, hand_info, img_w: int, img_h: int):
        """
        Single-Hand control mode:
          - Steering: Tilt angle of wrist-to-middle-finger axis
          - Throttle: Open palm (4-5 fingers)
          - Brake: Closed fist (0 fingers)
        """
        lm = hand_info["landmarks"].landmark
        # Vector from wrist (0) to middle finger MCP (9)
        wx, wy = lm[0].x * img_w, lm[0].y * img_h
        mx, my = lm[9].x * img_w, lm[9].y * img_h

        dx = mx - wx
        dy = my - wy  # usually negative (pointing up)

        # Angle from vertical (straight up = 0 deg)
        angle_rad = math.atan2(dx, -dy)
        angle_deg = math.degrees(angle_rad)

        raw_steer = angle_deg / 30.0  # 30 deg hand tilt for full turn
        raw_steer = max(-1.0, min(1.0, raw_steer))

        fingers = hand_info["extended_count"]

        if fingers >= 4:
            # Open palm -> Throttle
            raw_throttle = 0.85
            raw_brake = 0.0
            panic = False
            desc = "GAS (OPEN PALM)"
        elif fingers == 0:
            # Closed fist -> Stop
            raw_throttle = 0.0
            raw_brake = 1.0
            panic = False
            desc = "STOP / BRAKE (FIST)"
        elif fingers == 2:
            # Two fingers (peace sign) -> Reverse
            raw_throttle = 0.0
            raw_brake = 0.0
            panic = False
            desc = "COASTING"
        else:
            raw_throttle = 0.0
            raw_brake = 0.0
            panic = False
            desc = "IDLE"

        return raw_steer, raw_throttle, raw_brake, panic, desc

    def run(self):
        """Main webcam capture and recognition loop."""
        cap = cv2.VideoCapture(self.camera_idx)
        if not cap.isOpened():
            print(f"[Error] Could not open webcam (index {self.camera_idx}).")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

        print("=" * 65)
        print("  HAND GESTURE VEHICLE CONTROLLER (PART A)")
        print(f"  Streaming UDP packets to: {self.target_ip}:{self.target_port}")
        print("  Press 'Q' on the camera window to exit.")
        print("=" * 65)

        prev_time = time.time()

        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    print("[Warning] Empty camera frame.")
                    continue

                # Flip horizontally for natural mirror selfie view
                frame = cv2.flip(frame, 1)
                img_h, img_w, _ = frame.shape

                # Convert BGR to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)

                target_steer = 0.0
                target_throttle = 0.0
                target_brake = 0.0
                panic_stop = False
                status_text = "NO HANDS DETECTED (IDLE)"

                hands_data = []

                if results.multi_hand_landmarks:
                    for i, h_lm in enumerate(results.multi_hand_landmarks):
                        # Draw standard landmarks
                        self.mp_draw.draw_landmarks(
                            frame,
                            h_lm,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_styles.get_default_hand_landmarks_style(),
                            self.mp_styles.get_default_hand_connections_style()
                        )

                        # Determine if right or left hand label from MediaPipe
                        hand_label = "Right"
                        if results.multi_handedness and len(results.multi_handedness) > i:
                            hand_label = results.multi_handedness[i].classification[0].label

                        # In selfie view, mirror handedness
                        is_right = (hand_label == "Right")

                        wrist = h_lm.landmark[0]
                        wrist_px = (int(wrist.x * img_w), int(wrist.y * img_h))
                        extended = self.count_extended_fingers(h_lm, is_right)

                        hands_data.append({
                            "landmarks": h_lm,
                            "wrist_px": wrist_px,
                            "is_right": is_right,
                            "extended_count": extended,
                        })

                    # 1. Evaluate gestures based on hand count
                    if len(hands_data) >= 2:
                        target_steer, target_throttle, target_brake, panic_stop, status_text = self.process_two_hands(
                            hands_data, img_w, img_h
                        )
                        # Draw Virtual Steering Wheel Line connecting hands
                        p1 = hands_data[0]["wrist_px"]
                        p2 = hands_data[1]["wrist_px"]
                        wheel_col = (0, 0, 255) if panic_stop else ((0, 255, 0) if target_throttle > 0 else (255, 200, 0))
                        cv2.line(frame, p1, p2, wheel_col, 4)
                        center_pt = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                        cv2.circle(frame, center_pt, 25, wheel_col, 3)

                    elif len(hands_data) == 1:
                        target_steer, target_throttle, target_brake, panic_stop, status_text = self.process_single_hand(
                            hands_data[0], img_w, img_h
                        )

                # Exponential smoothing to prevent webcam jitter
                a = self.steer_smoothing_alpha
                self.smooth_steer = a * target_steer + (1 - a) * self.smooth_steer
                self.smooth_throttle = a * target_throttle + (1 - a) * self.smooth_throttle
                self.smooth_brake = a * target_brake + (1 - a) * self.smooth_brake

                # 2. Send UDP packet to simulator
                self.client.send(
                    steering_angle=self.smooth_steer,
                    throttle=self.smooth_throttle,
                    brake=self.smooth_brake,
                    panic_stop=panic_stop
                )

                # 3. Render Visual HUD Overlay on Camera Frame
                fps = 1.0 / max(0.001, time.time() - prev_time)
                prev_time = time.time()
                self._draw_hud(frame, status_text, fps, panic_stop)

                # Show live video window
                cv2.imshow("Hand Gesture Vehicle Controller (Part A)", frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.client.close()
            print("[GestureController] Exited.")

    def _draw_hud(self, frame, status_text: str, fps: float, panic: bool):
        """Draws telemetry bars and gesture state overlay on the camera frame."""
        h, w, _ = frame.shape

        # Top Bar Background
        cv2.rectangle(frame, (0, 0), (w, 70), (20, 25, 35), -1)
        cv2.line(frame, (0, 70), (w, 70), (50, 70, 90), 2)

        # Status & Panic Alert
        status_col = (0, 0, 255) if panic else (0, 255, 120)
        cv2.putText(frame, f"STATE: {status_text}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_col, 2)
        cv2.putText(frame, f"FPS: {int(fps)} | Target: {self.target_ip}:{self.target_port}", (20, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 190, 200), 1)

        # Telemetry Gauges (Bottom Left)
        cv2.rectangle(frame, (15, h - 95), (280, h - 15), (20, 25, 35), -1)
        cv2.rectangle(frame, (15, h - 95), (280, h - 15), (50, 70, 90), 1)

        # Steer Gauge
        steer_pct = int(self.smooth_steer * 100)
        cv2.putText(frame, f"STEER: {steer_pct:+d}%", (25, h - 72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 220, 0), 1)
        cv2.rectangle(frame, (130, h - 80), (260, h - 68), (40, 50, 65), -1)
        center_x = 195
        offset = int(self.smooth_steer * 65)
        cv2.line(frame, (center_x, h - 80), (center_x, h - 68), (255, 255, 255), 1)
        cv2.rectangle(frame, (center_x, h - 80), (center_x + offset, h - 68), (255, 220, 0), -1)

        # Throttle Bar (Green)
        cv2.putText(frame, f"THROTTLE: {int(self.smooth_throttle*100)}%", (25, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 120), 1)
        cv2.rectangle(frame, (130, h - 58), (260, h - 46), (40, 50, 65), -1)
        fill_t = int(130 * self.smooth_throttle)
        cv2.rectangle(frame, (130, h - 58), (130 + fill_t, h - 46), (0, 255, 120), -1)

        # Brake Bar (Red)
        cv2.putText(frame, f"BRAKE: {int(self.smooth_brake*100)}%", (25, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 255), 1)
        cv2.rectangle(frame, (130, h - 36), (260, h - 24), (40, 50, 65), -1)
        fill_b = int(130 * self.smooth_brake)
        cv2.rectangle(frame, (130, h - 36), (130 + fill_b, h - 24), (80, 80, 255), -1)


def main():
    parser = argparse.ArgumentParser(description="Hand Gesture Vehicle Controller (Part A)")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Simulator UDP IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5005, help="Simulator UDP port (default: 5005)")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default: 0)")
    args = parser.parse_args()

    controller = HandGestureController(target_ip=args.ip, target_port=args.port, camera_idx=args.camera)
    controller.run()


if __name__ == "__main__":
    main()
