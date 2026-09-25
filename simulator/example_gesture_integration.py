"""Example Integration: How to connect your Hand Gesture Recognition code to the Simulator.

This file illustrates how to send continuous gesture data from your computer vision
pipeline (e.g., MediaPipe / OpenCV) to the Pygame Car Simulator.
"""
import time
from gesture_client import GestureClient

# 1. Initialize the UDP transmitter
# If running on the same PC: "127.0.0.1"
# If running on different laptops over Wi-Fi: use the Simulator PC's local IP (e.g. "192.168.1.15")
SIMULATOR_IP = "127.0.0.1"
SIMULATOR_PORT = 5005

client = GestureClient(target_ip=SIMULATOR_IP, target_port=SIMULATOR_PORT)

print(f"[Part A] Ready to transmit gesture packets to {SIMULATOR_IP}:{SIMULATOR_PORT}")


def process_gesture_frame():
    """
    In your real project, you get these values from MediaPipe hand landmarks / OpenCV:
      - Steering: Hand angle/tilt or horizontal offset (-1.0 to 1.0)
      - Throttle: Open palm / forward push (0.0 to 1.0)
      - Brake: Closed fist or two fingers (0.0 to 1.0)
      - Panic Stop: Both hands raised or cross sign (True / False)
    """
    pass


# Example: Simulating a camera frame loop
if __name__ == "__main__":
    try:
        print("[Part A] Streaming telemetry... (Press Ctrl+C to stop)")
        while True:
            # --- REPLACE THIS WITH YOUR REAL GESTURE RECOGNITION OUTPUT ---
            steering = 0.0     # -1.0 (left) to +1.0 (right)
            throttle = 0.6     # 0.0 to 1.0
            brake = 0.0        # 0.0 to 1.0
            panic = False      # True / False
            # -------------------------------------------------------------

            # Send the UDP packet once per detected camera frame
            client.send(
                steering_angle=steering,
                throttle=throttle,
                brake=brake,
                panic_stop=panic
            )

            # Match your camera FPS (e.g. 30 FPS = ~0.033s sleep)
            time.sleep(1.0 / 30.0)

    except KeyboardInterrupt:
        client.close()
        print("\n[Part A] Stream stopped.")
