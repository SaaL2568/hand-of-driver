"""Vehicle Entity, Visual Rendering, Skid Marks, and Visual Effects."""
import math
import pygame
from typing import List, Tuple
import config
from physics import CarPhysics


class SkidTrail:
    """Manages persistent tire skid marks left on the road surface."""
    def __init__(self, max_points: int = 400):
        self.max_points = max_points
        self.segments: List[Tuple[Tuple[float, float], Tuple[float, float], float]] = []  # (p1, p2, alpha)

    def add_segment(self, p1: Tuple[float, float], p2: Tuple[float, float], intensity: float = 1.0):
        self.segments.append((p1, p2, max(0.2, min(1.0, intensity))))
        if len(self.segments) > self.max_points:
            self.segments.pop(0)

    def clear(self):
        self.segments.clear()

    def render(self, surface: pygame.Surface, camera):
        for p1, p2, alpha in self.segments:
            if camera.is_point_in_view(p1[0], p1[1], margin=50):
                s1 = camera.world_to_screen(*p1)
                s2 = camera.world_to_screen(*p2)
                col = (30, 30, 35)
                pygame.draw.line(surface, col, s1, s2, 5)


class Car:
    """
    Complete Car GameObject containing physics state and graphical rendering.
    """
    def __init__(self, start_x: float = 0.0, start_y: float = 0.0, start_heading: float = 0.0):
        self.physics = CarPhysics(start_x, start_y, start_heading)
        self.skid_trail = SkidTrail()
        self.prev_rear_left: Tuple[float, float] = (0.0, 0.0)
        self.prev_rear_right: Tuple[float, float] = (0.0, 0.0)
        self.show_skids = True

    def reset(self, start_x: float, start_y: float, start_heading: float = 0.0):
        self.physics.reset(start_x, start_y, start_heading)
        self.skid_trail.clear()
        self._update_tire_positions()

    def update(
        self,
        dt: float,
        target_steer: float,
        throttle: float,
        brake: float,
        panic_stop: bool,
        reverse: float = 0.0,
        is_offroad: bool = False
    ):
        """Updates physics and updates skid trail."""
        self.physics.update(dt, target_steer, throttle, brake, panic_stop, reverse=reverse, is_offroad=is_offroad)

        # Update skid trail if skidding or heavy braking
        rear_l, rear_r = self._get_rear_tire_positions()
        if self.physics.is_skidding and self.show_skids:
            if self.prev_rear_left != (0.0, 0.0):
                self.skid_trail.add_segment(self.prev_rear_left, rear_l, self.physics.slip_ratio)
                self.skid_trail.add_segment(self.prev_rear_right, rear_r, self.physics.slip_ratio)
        
        self.prev_rear_left = rear_l
        self.prev_rear_right = rear_r

    def _get_rear_tire_positions(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Calculates world-space coordinates of the rear left and right tires."""
        cos_h = math.cos(self.physics.heading)
        sin_h = math.sin(self.physics.heading)
        half_w = config.CAR_WIDTH * 0.44
        rear_offset = -config.CAR_LENGTH * 0.32

        rl_x = self.physics.x + (rear_offset * cos_h - (-half_w) * sin_h)
        rl_y = self.physics.y + (rear_offset * sin_h + (-half_w) * cos_h)

        rr_x = self.physics.x + (rear_offset * cos_h - half_w * sin_h)
        rr_y = self.physics.y + (rear_offset * sin_h + half_w * cos_h)

        return (rl_x, rl_y), (rr_x, rr_y)

    def _update_tire_positions(self):
        rl, rr = self._get_rear_tire_positions()
        self.prev_rear_left = rl
        self.prev_rear_right = rr

    def render(self, surface: pygame.Surface, camera):
        """Renders tire tracks, headlight beams, vehicle body, wheels, and lights."""
        # 1. Skid marks under car
        if self.show_skids:
            self.skid_trail.render(surface, camera)

        # 2. Coordinates & rotation
        cos_h = math.cos(self.physics.heading)
        sin_h = math.sin(self.physics.heading)
        screen_pos = camera.world_to_screen(self.physics.x, self.physics.y)
        sx, sy = screen_pos

        # 3. Headlight glow cones
        self._render_headlights(surface, camera, cos_h, sin_h)

        # 4. Car Shadow
        shadow_poly = self._transform_poly(
            [
                (config.CAR_LENGTH * 0.52, -config.CAR_WIDTH * 0.52),
                (config.CAR_LENGTH * 0.52, config.CAR_WIDTH * 0.52),
                (-config.CAR_LENGTH * 0.52, config.CAR_WIDTH * 0.52),
                (-config.CAR_LENGTH * 0.52, -config.CAR_WIDTH * 0.52),
            ],
            cos_h, sin_h, sx + 5, sy + 7
        )
        shadow_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(shadow_surf, (0, 0, 0, 90), shadow_poly)
        surface.blit(shadow_surf, (0, 0))

        # 5. Steerable Front Wheels & Fixed Rear Wheels
        self._render_wheels(surface, camera, cos_h, sin_h)

        # 6. Car Body Chassis (Cyber sleek sports shape)
        body_local = [
            (config.CAR_LENGTH * 0.50, -config.CAR_WIDTH * 0.35),   # Front-Right nose
            (config.CAR_LENGTH * 0.50, config.CAR_WIDTH * 0.35),    # Front-Left nose
            (config.CAR_LENGTH * 0.30, config.CAR_WIDTH * 0.50),    # Front wheelarch
            (-config.CAR_LENGTH * 0.35, config.CAR_WIDTH * 0.50),   # Rear wheelarch
            (-config.CAR_LENGTH * 0.50, config.CAR_WIDTH * 0.40),   # Rear-Left
            (-config.CAR_LENGTH * 0.50, -config.CAR_WIDTH * 0.40),  # Rear-Right
            (-config.CAR_LENGTH * 0.35, -config.CAR_WIDTH * 0.50),  # Rear wheelarch
            (config.CAR_LENGTH * 0.30, -config.CAR_WIDTH * 0.50),   # Front wheelarch
        ]
        body_poly = self._transform_poly(body_local, cos_h, sin_h, sx, sy)
        pygame.draw.polygon(surface, config.COLOR_CAR_BODY, body_poly)
        pygame.draw.polygon(surface, (0, 80, 130), body_poly, 2)  # border

        # 7. Cockpit / Windshield Glass
        roof_local = [
            (config.CAR_LENGTH * 0.18, -config.CAR_WIDTH * 0.32),
            (config.CAR_LENGTH * 0.18, config.CAR_WIDTH * 0.32),
            (-config.CAR_LENGTH * 0.28, config.CAR_WIDTH * 0.36),
            (-config.CAR_LENGTH * 0.28, -config.CAR_WIDTH * 0.36),
        ]
        roof_poly = self._transform_poly(roof_local, cos_h, sin_h, sx, sy)
        pygame.draw.polygon(surface, config.COLOR_CAR_GLASS, roof_poly)
        pygame.draw.polygon(surface, config.COLOR_CAR_ROOF, roof_poly, 2)

        # Center roof stripe / accent
        stripe_local = [
            (config.CAR_LENGTH * 0.10, -config.CAR_WIDTH * 0.22),
            (config.CAR_LENGTH * 0.10, config.CAR_WIDTH * 0.22),
            (-config.CAR_LENGTH * 0.22, config.CAR_WIDTH * 0.25),
            (-config.CAR_LENGTH * 0.22, -config.CAR_WIDTH * 0.25),
        ]
        stripe_poly = self._transform_poly(stripe_local, cos_h, sin_h, sx, sy)
        pygame.draw.polygon(surface, config.COLOR_CAR_ACCENT, stripe_poly)

        # 8. Front Headlight Lenses
        hl_r = self._transform_point(config.CAR_LENGTH * 0.48, -config.CAR_WIDTH * 0.30, cos_h, sin_h, sx, sy)
        hl_l = self._transform_point(config.CAR_LENGTH * 0.48, config.CAR_WIDTH * 0.30, cos_h, sin_h, sx, sy)
        pygame.draw.circle(surface, config.COLOR_CAR_HEADLIGHT, hl_r, 4)
        pygame.draw.circle(surface, config.COLOR_CAR_HEADLIGHT, hl_l, 4)

        # 9. Tail / Brake Lights (Bright glow when braking or panic stopped)
        bl_col = config.COLOR_CAR_BRAKELIGHT if (self.physics.is_braking or self.physics.is_panic_stopped) else (110, 15, 15)
        bl_r = self._transform_point(-config.CAR_LENGTH * 0.48, -config.CAR_WIDTH * 0.32, cos_h, sin_h, sx, sy)
        bl_l = self._transform_point(-config.CAR_LENGTH * 0.48, config.CAR_WIDTH * 0.32, cos_h, sin_h, sx, sy)
        
        radius = 5 if (self.physics.is_braking or self.physics.is_panic_stopped) else 3
        pygame.draw.circle(surface, bl_col, bl_r, radius)
        pygame.draw.circle(surface, bl_col, bl_l, radius)

    def _render_headlights(self, surface: pygame.Surface, camera, cos_h: float, sin_h: float):
        """Draws soft cone projections for forward vehicle lighting."""
        screen_pos = camera.world_to_screen(self.physics.x, self.physics.y)
        sx, sy = screen_pos
        cone_len = 220.0
        cone_spread = 80.0

        for side in (-1, 1):
            start = self._transform_point(config.CAR_LENGTH * 0.48, side * config.CAR_WIDTH * 0.28, cos_h, sin_h, sx, sy)
            p_cone1 = self._transform_point(
                config.CAR_LENGTH * 0.48 + cone_len,
                side * config.CAR_WIDTH * 0.28 - cone_spread * 0.4,
                cos_h, sin_h, sx, sy
            )
            p_cone2 = self._transform_point(
                config.CAR_LENGTH * 0.48 + cone_len,
                side * config.CAR_WIDTH * 0.28 + cone_spread * 0.8,
                cos_h, sin_h, sx, sy
            )
            
            beam_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(beam_surf, (255, 255, 200, 22), [start, p_cone1, p_cone2])
            surface.blit(beam_surf, (0, 0))

    def _render_wheels(self, surface: pygame.Surface, camera, cos_h: float, sin_h: float):
        """Draws 4 wheels with steer angle applied to front pair."""
        screen_pos = camera.world_to_screen(self.physics.x, self.physics.y)
        sx, sy = screen_pos
        wheel_w, wheel_l = 6, 16

        # Wheel offsets: (local_x, local_y, is_front)
        wheels = [
            (config.CAR_LENGTH * 0.28, -config.CAR_WIDTH * 0.48, True),   # Front Right
            (config.CAR_LENGTH * 0.28, config.CAR_WIDTH * 0.48, True),    # Front Left
            (-config.CAR_LENGTH * 0.28, -config.CAR_WIDTH * 0.48, False), # Rear Right
            (-config.CAR_LENGTH * 0.28, config.CAR_WIDTH * 0.48, False),  # Rear Left
        ]

        for lx, ly, is_front in wheels:
            wheel_center = self._transform_point(lx, ly, cos_h, sin_h, sx, sy)
            
            # Wheel orientation angle
            angle = self.physics.heading + (self.physics.steer_angle if is_front else 0.0)
            w_cos = math.cos(angle)
            w_sin = math.sin(angle)

            # Wheel rect corners
            w_poly = [
                (wheel_center[0] + (wheel_l * 0.5 * w_cos - (-wheel_w * 0.5) * w_sin),
                 wheel_center[1] + (wheel_l * 0.5 * w_sin + (-wheel_w * 0.5) * w_cos)),
                (wheel_center[0] + (wheel_l * 0.5 * w_cos - (wheel_w * 0.5) * w_sin),
                 wheel_center[1] + (wheel_l * 0.5 * w_sin + (wheel_w * 0.5) * w_cos)),
                (wheel_center[0] + (-wheel_l * 0.5 * w_cos - (wheel_w * 0.5) * w_sin),
                 wheel_center[1] + (-wheel_l * 0.5 * w_sin + (wheel_w * 0.5) * w_cos)),
                (wheel_center[0] + (-wheel_l * 0.5 * w_cos - (-wheel_w * 0.5) * w_sin),
                 wheel_center[1] + (-wheel_l * 0.5 * w_sin + (-wheel_w * 0.5) * w_cos)),
            ]
            pygame.draw.polygon(surface, config.COLOR_CAR_TIRE, w_poly)

    def _transform_point(self, lx: float, ly: float, cos_h: float, sin_h: float, sx: int, sy: int) -> Tuple[int, int]:
        px = sx + (lx * cos_h - ly * sin_h)
        py = sy + (lx * sin_h + ly * cos_h)
        return (int(px), int(py))

    def _transform_poly(self, pts: List[Tuple[float, float]], cos_h: float, sin_h: float, sx: int, sy: int) -> List[Tuple[int, int]]:
        return [self._transform_point(lx, ly, cos_h, sin_h, sx, sy) for lx, ly in pts]
