"""Main Pygame Vehicle Simulator Application (Part B)."""
import argparse
import math
import sys
import time
from pathlib import Path
import pygame

import config
from car import Car
from horn import Horn
from hud import HUD
from network import UDPReceiver
from world import Camera, Track


def parse_arguments():
    """Parses optional CLI flags for network port, host, and resolution."""
    parser = argparse.ArgumentParser(description="Hand-Gesture Vehicle Simulator (Part B)")
    parser.add_argument("--host", type=str, default=config.DEFAULT_UDP_IP, help="UDP listening IP (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=config.DEFAULT_UDP_PORT, help="UDP listening port (default: 5005)")
    parser.add_argument("--keyboard-only", action="store_true", help="Start directly in manual keyboard mode")
    parser.add_argument("--width", type=int, default=config.SCREEN_WIDTH, help="Window width (default: 1280)")
    parser.add_argument("--height", type=int, default=config.SCREEN_HEIGHT, help="Window height (default: 720)")
    return parser.parse_args()


def main():
    args = parse_arguments()

    # 1. Initialize Pygame
    pygame.init()
    pygame.display.set_caption(config.WINDOW_TITLE)
    screen = pygame.display.set_mode((args.width, args.height), pygame.DOUBLEBUF | pygame.HWSURFACE)
    clock = pygame.time.Clock()

    # 2. Instantiate Components
    track = Track()
    start_x, start_y = track.start_pos
    start_heading = track.start_heading
    
    car = Car(start_x=start_x, start_y=start_y, start_heading=start_heading)
    camera = Camera(start_x, start_y, args.width, args.height)
    hud = HUD(args.width, args.height)
    horn = Horn()

    # 3. Start UDP Receiver
    receiver = UDPReceiver(host=args.host, port=args.port)
    receiver_started = receiver.start()
    if receiver_started:
        print(f"[Simulator] Listening for UDP gesture packets on {args.host}:{args.port}")
    else:
        print("[Simulator] Warning: Could not start UDP listener. Operating in Keyboard Fallback mode.")

    # Screenshots (F12 here, or P in the camera window for a matched camera+simulator pair)
    snap_dir = Path(__file__).resolve().parent.parent / "report_screenshots"
    snap_request = None
    last_snap_id = ""

    # Control State
    control_mode = "KEYBOARD" if args.keyboard_only else "NETWORK"
    running = True

    # 4. Simulation Loop
    try:
        while running:
            # Time delta capped to avoid huge delta jumps on lag spikes
            dt = min(0.05, clock.tick(config.FPS) / 1000.0)

            # -------------------------------------------------------------
            # A. Process Window & Keyboard Events
            # -------------------------------------------------------------
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_TAB:
                        # Toggle between network and manual keyboard override
                        control_mode = "KEYBOARD" if control_mode == "NETWORK" else "NETWORK"
                        print(f"[Simulator] Input mode switched to: {control_mode}")
                    elif event.key == pygame.K_r:
                        # Reset car to starting grid
                        car.reset(start_x, start_y, start_heading)
                    elif event.key == pygame.K_h:
                        hud.show_help = not hud.show_help
                    elif event.key == pygame.K_t:
                        car.show_skids = not car.show_skids
                    elif event.key == pygame.K_m:
                        hud.show_minimap = not hud.show_minimap
                    elif event.key == pygame.K_F12:
                        snap_request = time.strftime("%Y%m%d_%H%M%S")

            # -------------------------------------------------------------
            # B. Read Keyboard Inputs (for Fallback / Manual Drive)
            # -------------------------------------------------------------
            keys = pygame.key.get_pressed()
            kb_throttle = 0.0
            kb_reverse = 0.0
            kb_brake = 0.0
            kb_steer = 0.0
            kb_panic = False

            if keys[pygame.K_w] or keys[pygame.K_UP]:
                kb_throttle = 1.0
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                kb_reverse = 1.0  # S = Dedicated Reverse
            if keys[pygame.K_SPACE]:
                kb_brake = 1.0    # Space = Dedicated Brake / Stop
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                kb_steer -= 1.0
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                kb_steer += 1.0
            if keys[pygame.K_p]:
                kb_panic = True

            keyboard_active = (kb_throttle > 0 or kb_reverse > 0 or kb_brake > 0 or kb_steer != 0 or kb_panic)

            # -------------------------------------------------------------
            # C. Input Arbitration (Network vs Keyboard Fallback)
            # -------------------------------------------------------------
            net_connected = receiver.is_connected()
            latest_cmd = receiver.get_latest_command()

            if control_mode == "NETWORK" and net_connected and latest_cmd:
                # Primary Gesture Control
                steer_input = latest_cmd.steering_angle
                throttle_input = latest_cmd.throttle
                brake_input = latest_cmd.brake
                reverse_input = kb_reverse  # keyboard reverse overlay
                panic_input = latest_cmd.panic_stop
                horn_input = latest_cmd.horn
                gear_select = "R" if latest_cmd.gear < 0 else "D"
                gesture_label = latest_cmd.gesture

                # Reverse gear (peace gesture): the throttle hand now drives backwards.
                # Physics treats reverse as a brake while still rolling forward, so
                # shifting while moving slows the car first, then reverses - no jerk.
                if latest_cmd.gear < 0:
                    reverse_input = max(reverse_input, throttle_input)
                    throttle_input = 0.0
                
                # Manual keyboard override: if user presses panic on keyboard, honor it
                if kb_panic:
                    panic_input = True
                if kb_brake > 0:
                    brake_input = max(brake_input, kb_brake)
            else:
                # Standalone Keyboard Fallback
                steer_input = kb_steer
                throttle_input = kb_throttle
                reverse_input = kb_reverse
                brake_input = kb_brake
                panic_input = kb_panic
                horn_input = False  # horn is gesture-only
                gear_select = None
                gesture_label = ""

            horn.set(horn_input)

            # -------------------------------------------------------------
            # D. Physics & Vehicle Update
            # -------------------------------------------------------------
            is_offroad = track.check_offroad(car.physics.x, car.physics.y)
            car.update(
                dt=dt,
                target_steer=steer_input,
                throttle=throttle_input,
                brake=brake_input,
                panic_stop=panic_input,
                reverse=reverse_input,
                is_offroad=is_offroad,
            )

            # -------------------------------------------------------------
            # E. Camera Tracking Update
            # -------------------------------------------------------------
            car_vx = math.cos(car.physics.heading) * car.physics.velocity
            car_vy = math.sin(car.physics.heading) * car.physics.velocity
            camera.update(dt, car.physics.x, car.physics.y, car_vx, car_vy)

            # -------------------------------------------------------------
            # F. Rendering Passes
            # -------------------------------------------------------------
            # 1. Environment & Track
            track.render(screen, camera)

            # 2. Vehicle (Skids, Shadow, Body, Lights)
            car.render(screen, camera)

            # 3. Telemetry HUD & Diagnostics Overlay
            net_stats = receiver.get_stats()
            hud.render(
                surface=screen,
                physics=car.physics,
                track=track,
                net_stats=net_stats,
                control_mode=control_mode,
                steer_input=steer_input,
                throttle_input=throttle_input,
                brake_input=brake_input,
                panic_input=panic_input,
                reverse_input=reverse_input,
                fps=clock.get_fps(),
                horn_input=horn_input,
                gear_select=gear_select,
                gesture_label=gesture_label,
            )

            # Save a screenshot when asked (camera P key sends a snap id in its packets)
            if control_mode == "NETWORK" and latest_cmd and latest_cmd.snap and latest_cmd.snap != last_snap_id:
                last_snap_id = latest_cmd.snap
                snap_request = latest_cmd.snap
            if snap_request:
                try:
                    snap_dir.mkdir(parents=True, exist_ok=True)
                    path = snap_dir / f"{snap_request}_simulator.png"
                    pygame.image.save(screen, str(path))
                    print(f"[Simulator] Screenshot saved: {path}")
                except (OSError, pygame.error) as err:
                    print(f"[Simulator] Screenshot failed: {err}")
                snap_request = None

            pygame.display.flip()

    finally:
        # Clean cleanup
        horn.set(False)
        receiver.stop()
        pygame.quit()
        print("[Simulator] Exited cleanly.")


if __name__ == "__main__":
    main()
