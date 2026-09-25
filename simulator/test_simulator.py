"""Automated Test Suite for the Car Simulator Components."""
import json
import math
import os
import socket
import time
import unittest
import pygame

import config
from car import Car
from hud import HUD
from network import UDPReceiver, VehicleCommand
from physics import CarPhysics
from world import Camera, Track


class TestPhysicsModel(unittest.TestCase):
    def setUp(self):
        self.physics = CarPhysics(x=0, y=0, heading=0)

    def test_acceleration_forward(self):
        """Verify throttle increases forward velocity."""
        initial_v = self.physics.velocity
        self.physics.update(dt=0.1, target_steer_norm=0.0, throttle=1.0, brake=0.0, panic_stop=False)
        self.assertGreater(self.physics.velocity, initial_v)
        self.assertGreater(self.physics.x, 0)

    def test_panic_stop_deceleration(self):
        """Verify panic stop overrides throttle and rapidly brings car to a stop."""
        self.physics.velocity = 500.0  # high speed
        self.physics.update(dt=0.1, target_steer_norm=0.0, throttle=1.0, brake=0.0, panic_stop=True)
        # Should decelerate despite throttle=1.0
        self.assertLess(self.physics.velocity, 500.0)
        self.assertTrue(self.physics.is_panic_stopped)

    def test_steering_kinematics(self):
        """Verify non-zero steering changes vehicle heading when in motion."""
        self.physics.velocity = 300.0
        initial_heading = self.physics.heading
        # Steer right (+1.0)
        self.physics.update(dt=0.2, target_steer_norm=1.0, throttle=0.5, brake=0.0, panic_stop=False)
        self.assertNotEqual(self.physics.heading, initial_heading)

    def test_max_steering_angle_limit(self):
        """Verify maximum steering angle is limited to 20 degrees."""
        self.assertAlmostEqual(math.degrees(config.MAX_STEERING_ANGLE), 20.0, places=1)
        # Apply full steering lock (+1.0) over enough time to reach steady state
        self.physics.update(dt=1.0, target_steer_norm=1.0, throttle=0.0, brake=0.0, panic_stop=False)
        self.assertAlmostEqual(math.degrees(self.physics.steer_angle), 20.0, places=1)
        # Apply full left steering lock (-1.0)
        self.physics.update(dt=1.0, target_steer_norm=-1.0, throttle=0.0, brake=0.0, panic_stop=False)
        self.assertAlmostEqual(math.degrees(self.physics.steer_angle), -20.0, places=1)

    def test_brake_stops_vehicle(self):
        """Verify brake decelerates vehicle to 0 and stops without going in reverse."""
        self.physics.velocity = 100.0
        self.physics.update(dt=0.3, target_steer_norm=0.0, throttle=0.0, brake=1.0, panic_stop=False, reverse=0.0)
        # Should decelerate towards 0
        self.assertLess(self.physics.velocity, 100.0)
        self.assertGreaterEqual(self.physics.velocity, 0.0)

    def test_reverse_gear(self):
        """Verify reverse input accelerates vehicle backward."""
        self.physics.velocity = 0.0
        self.physics.update(dt=0.2, target_steer_norm=0.0, throttle=0.0, brake=0.0, panic_stop=False, reverse=1.0)
        self.assertLess(self.physics.velocity, 0.0)
        self.assertTrue(self.physics.is_reversing)

    def test_offroad_damping(self):
        """Verify offroad applies extra friction and limits max speed."""
        self.physics.velocity = 500.0
        self.physics.update(dt=0.1, target_steer_norm=0.0, throttle=0.0, brake=0.0, panic_stop=False, is_offroad=True)
        self.assertLess(self.physics.velocity, 500.0)


class TestNetworkReceiver(unittest.TestCase):
    def setUp(self):
        self.test_port = 5991
        self.receiver = UDPReceiver(host="127.0.0.1", port=self.test_port)
        self.assertTrue(self.receiver.start())
        time.sleep(0.05)

    def tearDown(self):
        self.receiver.stop()

    def test_valid_packet_reception(self):
        """Verify valid JSON packet is received, parsed, and stored."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = {
            "steeringAngle": -0.65,
            "throttle": 0.85,
            "brake": 0.0,
            "panicStop": False,
            "timestamp": time.time(),
        }
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", self.test_port))
        sock.close()

        # Wait for receiver thread
        time.sleep(0.1)
        cmd = self.receiver.get_latest_command()
        self.assertIsNotNone(cmd)
        self.assertAlmostEqual(cmd.steering_angle, -0.65, places=2)
        self.assertAlmostEqual(cmd.throttle, 0.85, places=2)
        self.assertEqual(cmd.panic_stop, False)
        self.assertTrue(self.receiver.is_connected())

    def test_malformed_packet_handling(self):
        """Verify bad packets don't crash receiver and are logged."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"INVALID_NON_JSON_DATA", ("127.0.0.1", self.test_port))
        sock.close()

        time.sleep(0.1)
        stats = self.receiver.get_stats()
        self.assertGreaterEqual(stats["malformed_count"], 1)


class TestWorldAndTrack(unittest.TestCase):
    def test_track_generation(self):
        track = Track()
        self.assertGreater(len(track.centerline), 50)
        self.assertIsNotNone(track.start_pos)

        # On-road check near start
        sx, sy = track.start_pos
        self.assertTrue(track.is_point_on_road(sx, sy))

        # Far off-road check
        self.assertFalse(track.is_point_on_road(9999, 9999))

    def test_sharp_90_degree_corners_no_curves(self):
        """Verify that all city track segments are strictly orthogonal (0° or 90° lines, no curves)."""
        track = Track()
        self.assertGreaterEqual(len(track.corner_points), 8)
        
        for (x1, y1), (x2, y2) in track.segments:
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            # Must be either strictly horizontal (dy == 0) or strictly vertical (dx == 0)
            is_orthogonal = (dx < 0.001 and dy > 0.001) or (dy < 0.001 and dx > 0.001)
            self.assertTrue(is_orthogonal, f"Segment ({x1},{y1}) -> ({x2},{y2}) is not strictly orthogonal (sharp 90°)")

    def test_city_buildings_generation(self):
        """Verify city buildings are populated and do not block the road."""
        track = Track()
        self.assertGreater(len(track.buildings), 5)
        for b in track.buildings:
            # Building centers must not be on the road
            self.assertFalse(track.is_point_on_road(b.rect.centerx, b.rect.centery))

    def test_camera_projection(self):
        cam = Camera(x=500, y=500, screen_w=1280, screen_h=720)
        sx, sy = cam.world_to_screen(500, 500)
        self.assertEqual(sx, 640)
        self.assertEqual(sy, 360)


class TestHeadlessRenderPass(unittest.TestCase):
    def test_render_all_components(self):
        """Verify all graphics draw routines execute cleanly on a headless Pygame surface."""
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        surface = pygame.Surface((1280, 720))

        track = Track()
        car = Car(start_x=track.start_pos[0], start_y=track.start_pos[1], start_heading=track.start_heading)
        camera = Camera(track.start_pos[0], track.start_pos[1], 1280, 720)
        hud = HUD(1280, 720)

        # Step 1: Update
        car.update(0.016, target_steer=0.2, throttle=0.8, brake=0.0, panic_stop=False)
        camera.update(0.016, car.physics.x, car.physics.y, 100, 50)

        # Step 2: Render
        track.render(surface, camera)
        car.render(surface, camera)
        hud.render(
            surface=surface,
            physics=car.physics,
            track=track,
            net_stats={"is_connected": True, "packet_rate_hz": 30, "packet_count": 10},
            control_mode="NETWORK",
            steer_input=0.2,
            throttle_input=0.8,
            brake_input=0.0,
            panic_input=False,
            fps=60.0
        )

        pygame.quit()


if __name__ == "__main__":
    unittest.main()
