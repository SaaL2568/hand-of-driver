"""Mock UDP Packet Transmitter for Testing and Validation.

Simulates the gesture recognition subsystem by broadcasting JSON packets
matching the capstone network protocol:
{
  "steeringAngle": float (-1.0 to 1.0),
  "throttle": float (0.0 to 1.0),
  "brake": float (0.0 to 1.0),
  "panicStop": bool,
  "timestamp": float
}
"""
import argparse
import json
import math
import socket
import time
import sys


def send_packet(sock: socket.socket, addr: tuple, steering: float, throttle: float, brake: float, panic: bool):
    """Encodes and sends a single UDP telemetry packet."""
    payload = {
        "steeringAngle": round(max(-1.0, min(1.0, float(steering))), 3),
        "throttle": round(max(0.0, min(1.0, float(throttle))), 3),
        "brake": round(max(0.0, min(1.0, float(brake))), 3),
        "panicStop": bool(panic),
        "timestamp": time.time(),
    }
    raw_data = json.dumps(payload).encode("utf-8")
    sock.sendto(raw_data, addr)
    return payload


def run_auto_slalom(sock: socket.socket, addr: tuple, rate_hz: float):
    """Test scenario: Continuous smooth slalom turns at 70% throttle."""
    print("[MockSender] Running AUTOMATED SLALOM test... (Press Ctrl+C to stop)")
    start_t = time.time()
    interval = 1.0 / rate_hz

    try:
        while True:
            elapsed = time.time() - start_t
            # Sinusoidal steering wave
            steer = math.sin(elapsed * 2.2) * 0.75
            throttle = 0.70
            brake = 0.0
            panic = False

            p = send_packet(sock, addr, steer, throttle, brake, panic)
            print(f"\r[TX] Steer: {p['steeringAngle']:+0.2f} | Thr: {p['throttle']:.2f} | Brk: {p['brake']:.2f} | Panic: {p['panicStop']}", end="", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[MockSender] Stopped.")


def run_auto_panic_test(sock: socket.socket, addr: tuple, rate_hz: float):
    """Test scenario: Accelerate for 3.5s then trigger emergency panic stop for 2s."""
    print("[MockSender] Running AUTOMATED ACCEL + PANIC STOP test... (Press Ctrl+C to stop)")
    interval = 1.0 / rate_hz

    try:
        while True:
            # 1. Acceleration Phase (3.5 seconds)
            print("\n>>> Phase 1: Accelerating (Throttle = 1.0)...")
            t_phase = time.time()
            while time.time() - t_phase < 3.5:
                send_packet(sock, addr, steering=0.0, throttle=1.0, brake=0.0, panic=False)
                time.sleep(interval)

            # 2. Panic Stop Trigger (2.0 seconds)
            print(">>> Phase 2: TRIGGERING PANIC STOP! (panicStop = True)...")
            t_phase = time.time()
            while time.time() - t_phase < 2.0:
                send_packet(sock, addr, steering=0.0, throttle=0.0, brake=1.0, panic=True)
                time.sleep(interval)

            # 3. Recovery Phase (1.5 seconds)
            print(">>> Phase 3: Released (Coasting)...")
            t_phase = time.time()
            while time.time() - t_phase < 1.5:
                send_packet(sock, addr, steering=0.0, throttle=0.0, brake=0.0, panic=False)
                time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[MockSender] Stopped.")


def run_interactive_terminal(sock: socket.socket, addr: tuple, rate_hz: float):
    """
    Interactive test mode using keyboard input via msvcrt on Windows.
    """
    import msvcrt

    print("=" * 65)
    print(" INTERACTIVE MOCK GESTURE SENDER (Windows Console)")
    print("=" * 65)
    print(" Controls:")
    print("   [W] Gas (+Throttle)       [S] Brake")
    print("   [A] Steer Left            [D] Steer Right")
    print("   [C] Center Steering       [X] Release All Pedals")
    print("   [P] Toggle Panic Stop     [Q] Quit")
    print("=" * 65)

    steer = 0.0
    throttle = 0.0
    brake = 0.0
    panic = False
    interval = 1.0 / rate_hz

    try:
        while True:
            # Check for non-blocking keypresses
            if msvcrt.kbhit():
                ch = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                if ch == "q":
                    break
                elif ch == "w":
                    throttle = min(1.0, throttle + 0.25)
                    brake = 0.0
                elif ch == "s":
                    brake = min(1.0, brake + 0.25)
                    throttle = 0.0
                elif ch == "a":
                    steer = max(-1.0, steer - 0.25)
                elif ch == "d":
                    steer = min(1.0, steer + 0.25)
                elif ch == "c":
                    steer = 0.0
                elif ch == "x":
                    throttle = 0.0
                    brake = 0.0
                elif ch == "p":
                    panic = not panic
                    if panic:
                        throttle = 0.0
                        brake = 1.0

            # Naturally decay throttle / brake slightly when no key pressed for realism
            p = send_packet(sock, addr, steer, throttle, brake, panic)
            status = f"\r[TX] Steer: {p['steeringAngle']:+0.2f} | Thr: {p['throttle']:0.2f} | Brk: {p['brake']:0.2f} | Panic: {p['panicStop']}"
            print(status, end="", flush=True)
            time.sleep(interval)

    except KeyboardInterrupt:
        pass
    print("\n[MockSender] Stopped.")


def main():
    parser = argparse.ArgumentParser(description="Mock Gesture UDP Packet Transmitter")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target UDP host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5005, help="Target UDP port (default: 5005)")
    parser.add_argument("--rate", type=float, default=30.0, help="Packet broadcast rate in Hz (default: 30)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="interactive",
        choices=["interactive", "slalom", "panic", "circle"],
        help="Test scenario to execute",
    )

    args = parser.parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_addr = (args.host, args.port)

    print(f"[MockSender] Target configured -> {args.host}:{args.port} @ {args.rate} Hz")

    if args.scenario == "slalom":
        run_auto_slalom(sock, target_addr, args.rate)
    elif args.scenario == "panic":
        run_auto_panic_test(sock, target_addr, args.rate)
    elif args.scenario == "circle":
        print("[MockSender] Running CIRCLE test (Steer=0.5, Thr=0.6)...")
        interval = 1.0 / args.rate
        while True:
            send_packet(sock, target_addr, steering=0.5, throttle=0.6, brake=0.0, panic=False)
            time.sleep(interval)
    else:
        run_interactive_terminal(sock, target_addr, args.rate)


if __name__ == "__main__":
    main()
