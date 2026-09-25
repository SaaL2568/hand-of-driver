"""Helper library for Part A (Gesture Recognition) to send control packets to Part B (Simulator).

Example Usage in your OpenCV/MediaPipe gesture recognition script:
------------------------------------------------------------------
from gesture_client import GestureClient

# Initialize client (points to localhost:5005 or remote IP)
client = GestureClient(target_ip="127.0.0.1", target_port=5005)

# Inside your camera frame processing loop:
client.send(
    steering_angle=0.45,   # float -1.0 (left) to 1.0 (right)
    throttle=0.80,         # float 0.0 (idle) to 1.0 (full gas)
    brake=0.0,             # float 0.0 to 1.0
    panic_stop=False       # bool (True = emergency cutoff)
)
"""
import json
import socket
import time


class GestureClient:
    """Lightweight UDP client to stream gesture telemetry to the vehicle simulator."""
    def __init__(self, target_ip: str = "127.0.0.1", target_port: int = 5005):
        self.target_ip = target_ip
        self.target_port = target_port
        self.target_addr = (self.target_ip, self.target_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(
        self,
        steering_angle: float = 0.0,
        throttle: float = 0.0,
        brake: float = 0.0,
        panic_stop: bool = False,
        gear: int = 1,
        horn: bool = False,
        gesture: str = "",
        snap: str = "",
    ) -> bool:
        """
        Broadcasts a validated telemetry packet.
        
        Args:
            steering_angle: float between -1.0 (left) and 1.0 (right)
            throttle: float between 0.0 (idle) and 1.0 (max gas)
            brake: float between 0.0 (none) and 1.0 (full brake)
            panic_stop: boolean emergency stop trigger
            gear: 1 = forward (D), -1 = reverse (R)
            horn: True while the horn is held
            gesture: latest static-gesture label (for the simulator HUD)
        """
        try:
            payload = {
                "steeringAngle": round(max(-1.0, min(1.0, float(steering_angle))), 4),
                "throttle": round(max(0.0, min(1.0, float(throttle))), 4),
                "brake": round(max(0.0, min(1.0, float(brake))), 4),
                "panicStop": bool(panic_stop),
                "gear": -1 if gear < 0 else 1,
                "horn": bool(horn),
                "gesture": str(gesture)[:32],
                "snap": str(snap)[:40],   # screenshot request id (simulator saves a matching frame)
                "timestamp": time.time(),
            }
            raw_bytes = json.dumps(payload).encode("utf-8")
            self.sock.sendto(raw_bytes, self.target_addr)
            return True
        except Exception as e:
            print(f"[GestureClient] Error sending packet: {e}")
            return False

    def close(self):
        """Closes the underlying UDP socket."""
        try:
            self.sock.close()
        except Exception:
            pass
