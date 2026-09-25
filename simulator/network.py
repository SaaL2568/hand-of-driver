"""UDP Network Receiver for Hand-Gesture Telemetry Packets."""
import json
import socket
import threading
import time
from typing import Optional, Dict, Any, Tuple
import config


class VehicleCommand:
    """Represents a validated vehicle control packet."""
    def __init__(
        self,
        steering_angle: float = 0.0,
        throttle: float = 0.0,
        brake: float = 0.0,
        panic_stop: bool = False,
        client_timestamp: float = 0.0,
        received_timestamp: float = 0.0,
        gear: int = 1,
        horn: bool = False,
        gesture: str = "",
        snap: str = "",
    ):
        self.steering_angle = max(-1.0, min(1.0, float(steering_angle)))
        self.throttle = max(0.0, min(1.0, float(throttle)))
        self.brake = max(0.0, min(1.0, float(brake)))
        self.panic_stop = bool(panic_stop)
        self.gear = -1 if int(gear) < 0 else 1   # 1 = forward (D), -1 = reverse (R)
        self.horn = bool(horn)
        self.gesture = str(gesture)[:32]
        self.snap = str(snap)[:40]
        self.client_timestamp = float(client_timestamp)
        self.received_timestamp = received_timestamp or time.time()

    @property
    def latency_ms(self) -> float:
        """Calculate transmission latency if timestamps are synchronized, else 0."""
        if self.client_timestamp > 0:
            diff = (self.received_timestamp - self.client_timestamp) * 1000.0
            return max(0.0, min(9999.0, diff))
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steeringAngle": self.steering_angle,
            "throttle": self.throttle,
            "brake": self.brake,
            "panicStop": self.panic_stop,
            "gear": self.gear,
            "horn": self.horn,
            "gesture": self.gesture,
            "timestamp": self.client_timestamp,
            "receivedTimestamp": self.received_timestamp,
        }


class UDPReceiver:
    """
    Asynchronous, non-blocking UDP receiver for gesture control packets.
    Runs on a dedicated daemon thread and provides thread-safe access.
    """
    def __init__(self, host: str = config.DEFAULT_UDP_IP, port: int = config.DEFAULT_UDP_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Telemetry State
        self._latest_command: Optional[VehicleCommand] = None
        self._last_packet_time: float = 0.0
        self._packet_count: int = 0
        self._malformed_count: int = 0
        self._last_sender_addr: Optional[Tuple[str, int]] = None
        self._recent_packet_times = []  # used for packet rate (Hz) calculation

    def start(self) -> bool:
        """Binds the UDP socket and starts the listener thread."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.settimeout(0.5)  # 500ms timeout for graceful thread shutdown
            self.sock.bind((self.host, self.port))
            
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="UDPReceiverThread")
            self._thread.start()
            return True
        except Exception as err:
            print(f"[UDPReceiver] Failed to bind to {self.host}:{self.port} - Error: {err}")
            self.stop()
            return False

    def stop(self):
        """Stops the receiver thread and closes the socket."""
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def _listen_loop(self):
        """Worker loop listening for UDP packets."""
        while self._running:
            try:
                if not self.sock:
                    break
                data, addr = self.sock.recvfrom(config.SOCKET_BUFFER_SIZE)
                recv_time = time.time()
                self._process_raw_data(data, addr, recv_time)
            except socket.timeout:
                continue
            except OSError:
                # Socket was closed
                break
            except Exception as e:
                if self._running:
                    print(f"[UDPReceiver] Error receiving packet: {e}")

    def _process_raw_data(self, raw_bytes: bytes, addr: Tuple[str, int], recv_time: float):
        """Decodes JSON and validates vehicle command fields."""
        try:
            text = raw_bytes.decode("utf-8").strip()
            payload = json.loads(text)

            # Extract fields with forgiving key aliases if needed
            steering = payload.get("steeringAngle", payload.get("steering_angle", payload.get("steering", 0.0)))
            throttle = payload.get("throttle", payload.get("gas", 0.0))
            brake = payload.get("brake", payload.get("braking", 0.0))
            panic = payload.get("panicStop", payload.get("panic_stop", payload.get("panic", False)))
            timestamp = payload.get("timestamp", payload.get("time", 0.0))
            # Optional fields (older senders omit them): default forward, no horn
            gear = payload.get("gear", 1)
            if isinstance(gear, str):
                gear = -1 if gear.strip().upper() in ("R", "REVERSE", "-1") else 1
            horn = payload.get("horn", False)
            gesture = payload.get("gesture", "")
            snap = payload.get("snap", "")

            cmd = VehicleCommand(
                steering_angle=float(steering),
                throttle=float(throttle),
                brake=float(brake),
                panic_stop=bool(panic),
                client_timestamp=float(timestamp),
                received_timestamp=recv_time,
                gear=int(gear),
                horn=bool(horn),
                gesture=gesture,
                snap=snap,
            )

            with self._lock:
                self._latest_command = cmd
                self._last_packet_time = recv_time
                self._packet_count += 1
                self._last_sender_addr = addr
                
                # Keep sliding window for Hz calculation (last 1 second)
                self._recent_packet_times.append(recv_time)
                cutoff = recv_time - 1.0
                while self._recent_packet_times and self._recent_packet_times[0] < cutoff:
                    self._recent_packet_times.pop(0)

        except Exception as parse_err:
            with self._lock:
                self._malformed_count += 1
            print(f"[UDPReceiver] Malformed packet from {addr}: {raw_bytes[:80]} -> {parse_err}")

    def get_latest_command(self) -> Optional[VehicleCommand]:
        """Returns the most recent vehicle command."""
        with self._lock:
            return self._latest_command

    def is_connected(self) -> bool:
        """Returns True if a packet was received within PACKET_TIMEOUT_SEC."""
        with self._lock:
            if self._last_packet_time == 0:
                return False
            return (time.time() - self._last_packet_time) <= config.PACKET_TIMEOUT_SEC

    def get_stats(self) -> Dict[str, Any]:
        """Returns network health telemetry for the HUD."""
        with self._lock:
            now = time.time()
            is_active = (now - self._last_packet_time) <= config.PACKET_TIMEOUT_SEC if self._last_packet_time > 0 else False
            hz = len(self._recent_packet_times) if is_active else 0
            age_sec = (now - self._last_packet_time) if self._last_packet_time > 0 else 999.0
            
            return {
                "running": self._running,
                "host": self.host,
                "port": self.port,
                "is_connected": is_active,
                "packet_rate_hz": hz,
                "packet_count": self._packet_count,
                "malformed_count": self._malformed_count,
                "last_sender": f"{self._last_sender_addr[0]}:{self._last_sender_addr[1]}" if self._last_sender_addr else "None",
                "packet_age_sec": age_sec,
                "last_command": self._latest_command.to_dict() if self._latest_command else None,
            }
