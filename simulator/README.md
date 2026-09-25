# Hand-Gesture Vehicle Simulator (Part B)

A standalone Python/Pygame vehicle simulation application designed for the capstone hand-gesture vehicle control system.

It receives real-time UDP telemetry control packets from the gesture-recognition subsystem (Part A), simulates realistic 2D vehicle kinematics, and renders the car, circuit track, and a live telemetry dashboard at 60 FPS.

---

## 🌟 Key Features

1. **UDP Telemetry Network Receiver (`network.py`)**:
   - High-performance, non-blocking UDP socket running on a dedicated daemon thread.
   - Watches for JSON packets matching `{ "steeringAngle": float, "throttle": float, "brake": float, "panicStop": bool, "timestamp": float }`.
   - Thread-safe command queue with packet rate (Hz), latency, and watchdog connection monitoring.
2. **Standalone Keyboard Fallback (`main.py`)**:
   - Seamless offline testing without requiring the vision process to be running.
   - Direct manual override with `[TAB]` switch or hotkey fallback.
3. **Kinematic Bicycle Vehicle Physics (`physics.py`)**:
   - 2D bicycle model with longitudinal acceleration, aerodynamic drag, rolling resistance, turning radius calculations, reverse gear, and off-road grass friction.
   - **Panic Stop Response**: Instant throttle cut-off, maximum emergency braking deceleration, and hazard visual alerts.
4. **City Road Network & Urban Environment (`world.py`)**:
   - Multi-block Manhattan-style rectilinear city street circuit with straight avenues and sharp 90-degree corner turns (zero curves).
   - Concrete sidewalks, pedestrian zebra crosswalks, traffic signals, street lamps, and architectural skyscrapers with 3D drop shadows and rooftop details.
   - Smooth velocity-lookahead tracking camera and high-precision off-road sidewalk detection.
5. **Interactive Telemetry Dashboard / HUD (`hud.py`)**:
   - Digital speedometer (KM/H & MPH) & gear indicator (`D`, `R`, `N`, `P`).
   - Animated steering wheel rotation dial with degree readout.
   - Throttle (green) and Brake (red) live visualizer bars.
   - Connection status badge (`CONNECTED [30 Hz]` / `KEYBOARD FALLBACK`).
   - Emergency "PANIC STOP" pulsing warning banner.
   - Real-time track radar minimap.
6. **Mock Packet Sender Utility (`mock_sender.py`)**:
   - Interactive CLI test harness and automated test scenarios (slalom maneuvers, emergency braking cycles, circle test).

---

## 🚀 Quick Start

### 1. Installation
Ensure Python 3.8+ is installed, then install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Launch the Simulator
Run the simulator on the default UDP port (`5005`):
```bash
python main.py
```

Optional CLI flags:
```bash
python main.py --port 5005 --host 0.0.0.0 --width 1280 --height 720
```

### 3. Test Network Stream using Mock Sender
Open a **second terminal** and launch the mock packet transmitter:

- **Interactive Manual Mode (Windows Keyboard Sender)**:
  ```bash
  python mock_sender.py --scenario interactive
  ```
- **Automated Slalom Steering Test**:
  ```bash
  python mock_sender.py --scenario slalom
  ```
- **Automated Acceleration & Panic Stop Cycle**:
  ```bash
  python mock_sender.py --scenario panic
  ```

---

## 📡 Network Protocol Specification (Part A ➔ Part B)

Packets are sent as UTF-8 encoded JSON strings over UDP:

```json
{
  "steeringAngle": 0.35,
  "throttle": 0.80,
  "brake": 0.0,
  "panicStop": false,
  "timestamp": 1726053892.124
}
```

### Field Definitions:
| Field | Type | Range / Format | Description |
| :--- | :--- | :--- | :--- |
| `steeringAngle` | `float` | `-1.0` to `1.0` | `-1.0` = Full Left, `0.0` = Centered, `1.0` = Full Right |
| `throttle` | `float` | `0.0` to `1.0` | `0.0` = Idle, `1.0` = Maximum acceleration |
| `brake` | `float` | `0.0` to `1.0` | `0.0` = Released, `1.0` = Full brake application |
| `panicStop` | `bool` | `true` / `false` | Emergency cutoff: immediately zeroes throttle & engages maximum stopping force |
| `timestamp` | `float` | Unix Epoch (seconds) | Client frame generation time for latency tracking |

---

## 🎮 Simulator Keybindings (Fallback / Controls)

| Key | Action |
| :--- | :--- |
| `W` or `Up Arrow` | Apply Throttle (Forward Acceleration) |
| `S` or `Down Arrow` | Dedicated Reverse Gear (Drive Backward) |
| `Spacebar` | Brake / Stop Vehicle (Brings car to a complete stop) |
| `A` or `Left Arrow` | Steer Left |
| `D` or `Right Arrow` | Steer Right |
| `P` | Trigger / Toggle Emergency Panic Stop |
| `TAB` | Toggle Input Mode (`NETWORK` ⟷ `KEYBOARD`) |
| `R` | Reset Car to Starting Grid |
| `H` | Show / Hide In-Game Help Dialog |
| `T` | Toggle Tire Skid Trails |
| `M` | Toggle Track Radar Minimap |
| `Esc` | Quit Application |

---

## 🧪 Running Automated Tests

Run the comprehensive unit test suite:
```bash
python test_simulator.py
```
