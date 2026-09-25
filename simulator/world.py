"""World, City Road Network, Dynamic Camera, and Urban Environment Rendering.

This module implements an urban city street network with straight avenues,
sharp 90-degree intersections (no curves), concrete sidewalks, crosswalks,
traffic signals, street lights, and architectural skyscrapers.
"""
import math
import random
from typing import List, Tuple, Dict, Any
import pygame
import config


class CityBuilding:
    """Represents an urban skyscraper or commercial building with rooftop details."""
    def __init__(self, rect: pygame.Rect, b_type: str = "office", height_tier: int = 2):
        self.rect = rect
        self.b_type = b_type
        self.height_tier = height_tier  # 1: Low-rise, 2: Mid-rise, 3: High-rise tower
        
        # Rooftop details
        rnd = random.Random(rect.x * 1000 + rect.y)
        self.roof_style = rnd.choice(["hvac", "helipad", "solar", "skylight", "antennae"])
        self.roof_color = rnd.choice([
            config.COLOR_BUILDING_ROOF_DARK,
            config.COLOR_BUILDING_ROOF_LIGHT,
            config.COLOR_BUILDING_ROOF_GLASS,
        ])
        self.accent_color = rnd.choice([
            config.COLOR_BUILDING_ACCENT_CYAN,
            config.COLOR_BUILDING_ACCENT_AMBER,
            (180, 200, 220),
            (220, 90, 90),
        ])
        self.has_neon_trim = rnd.random() < 0.4


class Track:
    """
    Constructs and renders a continuous city street circuit with straight avenues,
    sharp 90-degree turns, concrete sidewalks, crosswalks, traffic signals,
    and urban architecture.
    """
    def __init__(self, road_width: float = 180.0):
        self.road_width = road_width
        self.half_road = road_width / 2.0
        self.sidewalk_width = 32.0
        self.total_half_width = self.half_road + self.sidewalk_width

        # Corner nodes for the rectilinear city circuit (100% sharp 90-degree turns, NO curves)
        # All segments run strictly along the X or Y axis.
        self.corner_points: List[Tuple[float, float]] = [
            (400.0, 400.0),      # Node 0: Start Avenue (Eastbound)
            (1900.0, 400.0),     # Node 1: Sharp 90° Turn South (1st Ave & Tech Blvd)
            (1900.0, 1300.0),    # Node 2: Sharp 90° Turn East (Tech Blvd & Plaza Way)
            (3100.0, 1300.0),    # Node 3: Sharp 90° Turn South (Plaza Way & Metro Blvd)
            (3100.0, 2700.0),    # Node 4: Sharp 90° Turn West (Metro Blvd & South Pkwy)
            (1700.0, 2700.0),    # Node 5: Sharp 90° Turn North (South Pkwy & Financial St)
            (1700.0, 2000.0),    # Node 6: Sharp 90° Turn West (Financial St & Center Square)
            (700.0, 2000.0),     # Node 7: Sharp 90° Turn South (Center Square & Harbour Way)
            (700.0, 3100.0),     # Node 8: Sharp 90° Turn West (Harbour Way & West Dock St)
            (-500.0, 3100.0),    # Node 9: Sharp 90° Turn North (West Dock St & Outer Loop)
            (-500.0, 1400.0),    # Node 10: Sharp 90° Turn East (Outer Loop & Midtown Ave)
            (400.0, 1400.0),     # Node 11: Sharp 90° Turn North (Midtown Ave & Northlink)
        ]

        # Straight road segments (p1, p2)
        self.segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        n = len(self.corner_points)
        for i in range(n):
            self.segments.append((self.corner_points[i], self.corner_points[(i + 1) % n]))

        # High-resolution straight centerline points for radar, telemetry, and tracking
        self.centerline = self._generate_sharp_centerline(step_dist=18.0)
        
        # Start line position & initial heading (East along Start Avenue)
        self.start_pos = (self.corner_points[0][0] + 120.0, self.corner_points[0][1])
        self.start_heading = 0.0  # 0 radians = Facing East (+X direction)

        # Procedural City Elements
        self.buildings: List[CityBuilding] = self._generate_city_buildings()
        self.street_lamps: List[Tuple[float, float, float]] = self._generate_street_lamps()
        self.traffic_lights: List[Dict[str, Any]] = self._generate_traffic_lights()
        self.sidewalk_trees: List[Tuple[float, float, int]] = self._generate_sidewalk_trees()

    def _generate_sharp_centerline(self, step_dist: float = 18.0) -> List[Tuple[float, float]]:
        """Generates a dense sequence of points along strict straight lines with sharp corners."""
        smooth = []
        for p1, p2 in self.segments:
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            seg_len = math.hypot(dx, dy)
            steps = max(1, int(round(seg_len / step_dist)))
            for s in range(steps):
                t = s / steps
                smooth.append((p1[0] + dx * t, p1[1] + dy * t))
        return smooth

    def is_point_on_road(self, x: float, y: float, margin: float = 0.0) -> bool:
        """
        Returns True if (x, y) is within the asphalt surface of any city road segment
        or intersection box, including the specified margin.
        """
        allowable_dist = self.half_road + margin
        allowable_dist_sq = allowable_dist * allowable_dist

        for (x1, y1), (x2, y2) in self.segments:
            # Check horizontal segment
            if abs(y1 - y2) < 0.001:
                min_x = min(x1, x2) - self.half_road
                max_x = max(x1, x2) + self.half_road
                clamped_x = max(min_x, min(max_x, x))
                d_sq = (x - clamped_x) ** 2 + (y - y1) ** 2
                if d_sq <= allowable_dist_sq:
                    return True
            # Check vertical segment
            elif abs(x1 - x2) < 0.001:
                min_y = min(y1, y2) - self.half_road
                max_y = max(y1, y2) + self.half_road
                clamped_y = max(min_y, min(max_y, y))
                d_sq = (x - x1) ** 2 + (y - clamped_y) ** 2
                if d_sq <= allowable_dist_sq:
                    return True

        return False

    def check_offroad(self, car_x: float, car_y: float) -> bool:
        """Returns True if the car has driven off the asphalt road surface onto sidewalks or city lots."""
        return not self.is_point_on_road(car_x, car_y, margin=-10.0)

    def _generate_city_buildings(self) -> List[CityBuilding]:
        """Populates city blocks surrounded by roads with realistic architectural buildings."""
        buildings = []
        rnd = random.Random(101)

        # Candidate grid zones across the city expanse
        min_gx, max_gx = -900, 3600
        min_gy, max_gy = 0, 3600
        block_step = 280

        for bx in range(min_gx, max_gx, block_step):
            for by in range(min_gy, max_gy, block_step):
                # Sub-divide block into 1-3 buildings
                bw = rnd.randint(180, 240)
                bh = rnd.randint(180, 240)
                cx = bx + block_step // 2
                cy = by + block_step // 2

                # Verify building clearance from any road segment
                b_rect = pygame.Rect(cx - bw // 2, cy - bh // 2, bw, bh)
                safe = True
                clearance = self.total_half_width + 30.0

                # Check building corners and center against roads
                test_points = [
                    (b_rect.left, b_rect.top),
                    (b_rect.right, b_rect.top),
                    (b_rect.left, b_rect.bottom),
                    (b_rect.right, b_rect.bottom),
                    (b_rect.centerx, b_rect.centery),
                ]
                for px, py in test_points:
                    if self.is_point_on_road(px, py, margin=clearance - self.half_road):
                        safe = False
                        break

                if safe:
                    tier = rnd.choice([1, 2, 2, 3, 3])
                    b_type = rnd.choice(["office", "tower", "commercial", "plaza"])
                    buildings.append(CityBuilding(b_rect, b_type=b_type, height_tier=tier))

        return buildings

    def _generate_street_lamps(self) -> List[Tuple[float, float, float]]:
        """Generates street lamp coordinates (x, y, rotation) along sidewalks."""
        lamps = []
        spacing = 220.0
        offset = self.half_road + 14.0

        for (x1, y1), (x2, y2) in self.segments:
            dx = x2 - x1
            dy = y2 - y1
            seg_len = math.hypot(dx, dy)
            steps = max(2, int(seg_len / spacing))

            # Perpendicular normals
            nx = -dy / seg_len
            ny = dx / seg_len

            for s in range(1, steps):
                t = s / float(steps)
                cx = x1 + dx * t
                cy = y1 + dy * t
                # Left sidewalk lamp
                lamps.append((cx + nx * offset, cy + ny * offset, math.atan2(ny, nx)))
                # Right sidewalk lamp
                lamps.append((cx - nx * offset, cy - ny * offset, math.atan2(-ny, -nx)))

        return lamps

    def _generate_traffic_lights(self) -> List[Dict[str, Any]]:
        """Places traffic light posts at 90-degree corner intersections."""
        lights = []
        offset = self.half_road + 18.0

        for cx, cy in self.corner_points:
            # 4 corner quadrant posts for each intersection
            for qx, qy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
                lx = cx + qx * offset
                ly = cy + qy * offset
                lights.append({
                    "pos": (lx, ly),
                    "dir": (qx, qy)
                })
        return lights

    def _generate_sidewalk_trees(self) -> List[Tuple[float, float, int]]:
        """Places neat urban sidewalk planter trees between street lamps."""
        trees = []
        spacing = 180.0
        offset = self.half_road + 16.0

        for (x1, y1), (x2, y2) in self.segments:
            dx = x2 - x1
            dy = y2 - y1
            seg_len = math.hypot(dx, dy)
            steps = max(2, int(seg_len / spacing))
            nx = -dy / seg_len
            ny = dx / seg_len

            for s in range(1, steps):
                t = (s - 0.5) / float(steps)
                cx = x1 + dx * t
                cy = y1 + dy * t
                trees.append((cx + nx * offset, cy + ny * offset, 11))
                trees.append((cx - nx * offset, cy - ny * offset, 11))

        return trees

    def render(self, surface: pygame.Surface, camera: "Camera"):
        """Draws the complete city environment: asphalt avenues, sidewalks, crosswalks, buildings, and lights."""
        screen_w, screen_h = surface.get_size()

        # -------------------------------------------------------------
        # 1. Urban Concrete Ground & Pavement Grid
        # -------------------------------------------------------------
        surface.fill(config.COLOR_CITY_GROUND)

        cam_x, cam_y = camera.x, camera.y
        grid_size = 80
        start_gx = int(cam_x - screen_w / 2) // grid_size * grid_size
        start_gy = int(cam_y - screen_h / 2) // grid_size * grid_size

        for gx in range(start_gx, start_gx + screen_w + grid_size * 2, grid_size):
            for gy in range(start_gy, start_gy + screen_h + grid_size * 2, grid_size):
                if (gx // grid_size + gy // grid_size) % 2 == 0:
                    sx, sy = camera.world_to_screen(gx, gy)
                    rect = pygame.Rect(sx, sy, grid_size, grid_size)
                    pygame.draw.rect(surface, config.COLOR_CITY_GROUND_ACCENT, rect)
                    pygame.draw.rect(surface, (20, 24, 32), rect, 1)

        # -------------------------------------------------------------
        # 2. Sidewalk Surfaces (Concrete Pavements)
        # -------------------------------------------------------------
        for (x1, y1), (x2, y2) in self.segments:
            min_x, max_x = min(x1, x2), max(x1, x2)
            min_y, max_y = min(y1, y2), max(y1, y2)
            
            # Expand bounding box for sidewalk
            sw_rect_w = (max_x - min_x) + self.total_half_width * 2
            sw_rect_h = (max_y - min_y) + self.total_half_width * 2
            sw_world_x = min_x - self.total_half_width
            sw_world_y = min_y - self.total_half_width

            if camera.is_point_in_view(sw_world_x + sw_rect_w / 2, sw_world_y + sw_rect_h / 2, margin=sw_rect_w + 100):
                sx, sy = camera.world_to_screen(sw_world_x, sw_world_y)
                sw_rect = pygame.Rect(sx, sy, int(sw_rect_w), int(sw_rect_h))
                pygame.draw.rect(surface, config.COLOR_SIDEWALK, sw_rect)
                pygame.draw.rect(surface, config.COLOR_SIDEWALK_CURB, sw_rect, 2)

        # -------------------------------------------------------------
        # 3. Asphalt Road Network (Sharp Avenues & Intersection Boxes)
        # -------------------------------------------------------------
        for (x1, y1), (x2, y2) in self.segments:
            min_x, max_x = min(x1, x2), max(x1, x2)
            min_y, max_y = min(y1, y2), max(y1, y2)

            road_w = (max_x - min_x) + self.road_width
            road_h = (max_y - min_y) + self.road_width
            road_wx = min_x - self.half_road
            road_wy = min_y - self.half_road

            if camera.is_point_in_view(road_wx + road_w / 2, road_wy + road_h / 2, margin=road_w + 100):
                sx, sy = camera.world_to_screen(road_wx, road_wy)
                r_rect = pygame.Rect(sx, sy, int(road_w), int(road_h))
                pygame.draw.rect(surface, config.COLOR_ROAD, r_rect)
                pygame.draw.rect(surface, config.COLOR_ROAD_SHOULDER, r_rect, 2)

        # -------------------------------------------------------------
        # 4. Road Markings (Lane Dividers, Crosswalks, Stop Lines)
        # -------------------------------------------------------------
        for (x1, y1), (x2, y2) in self.segments:
            dx = x2 - x1
            dy = y2 - y1
            seg_len = math.hypot(dx, dy)
            if seg_len < 10:
                continue

            # Dashed Center Lane Marking
            dash_len = 24.0
            gap_len = 20.0
            step = dash_len + gap_len
            num_dashes = int((seg_len - self.road_width * 1.2) / step)
            start_dist = self.road_width * 0.6

            for d in range(num_dashes):
                t1 = (start_dist + d * step) / seg_len
                t2 = (start_dist + d * step + dash_len) / seg_len
                if t2 > 0.98:
                    break
                p_start = (x1 + dx * t1, y1 + dy * t1)
                p_end = (x1 + dx * t2, y1 + dy * t2)

                if camera.is_point_in_view(p_start[0], p_start[1], margin=50):
                    s1 = camera.world_to_screen(*p_start)
                    s2 = camera.world_to_screen(*p_end)
                    pygame.draw.line(surface, config.COLOR_LANE_MARKING, s1, s2, 3)

        # 5. Pedestrian Zebra Crosswalks at Sharp Turn Intersections
        stripe_w = 8.0
        stripe_gap = 6.0
        crosswalk_depth = 26.0

        for cx, cy in self.corner_points:
            if not camera.is_point_in_view(cx, cy, margin=self.road_width + 100):
                continue

            # Draw crosswalks on all 4 arms entering the intersection
            for arm_dx, arm_dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                # Position of crosswalk bar center
                cw_dist = self.half_road + crosswalk_depth / 2.0 + 2.0
                cw_x = cx + arm_dx * cw_dist
                cw_y = cy + arm_dy * cw_dist

                # Tangent / perpendicular for zebra stripes
                px = -arm_dy
                py = arm_dx

                span = self.half_road * 1.8
                num_stripes = int(span / (stripe_w + stripe_gap))

                for s in range(-num_stripes // 2, num_stripes // 2 + 1):
                    offset = s * (stripe_w + stripe_gap)
                    s_center_x = cw_x + px * offset
                    s_center_y = cw_y + py * offset

                    # Two endpoints of the stripe
                    p1 = (s_center_x - arm_dx * (crosswalk_depth / 2), s_center_y - arm_dy * (crosswalk_depth / 2))
                    p2 = (s_center_x + arm_dx * (crosswalk_depth / 2), s_center_y + arm_dy * (crosswalk_depth / 2))

                    sp1 = camera.world_to_screen(*p1)
                    sp2 = camera.world_to_screen(*p2)
                    pygame.draw.line(surface, config.COLOR_CROSSWALK, sp1, sp2, int(stripe_w))

        # -------------------------------------------------------------
        # 6. Start / Finish Line Checkpoint
        # -------------------------------------------------------------
        s_wx = self.start_pos[0]
        s_wy = self.start_pos[1]
        if camera.is_point_in_view(s_wx, s_wy, margin=self.road_width):
            # Checkered finish line
            top_pt = (s_wx, s_wy - self.half_road + 4)
            bot_pt = (s_wx, s_wy + self.half_road - 4)
            s_top = camera.world_to_screen(*top_pt)
            s_bot = camera.world_to_screen(*bot_pt)
            
            # Glowing Start Line
            pygame.draw.line(surface, config.COLOR_FINISH_LINE, s_top, s_bot, 8)
            pygame.draw.line(surface, (255, 255, 255), s_top, s_bot, 2)

        # -------------------------------------------------------------
        # 7. City Buildings & Architectural Skyscrapers
        # -------------------------------------------------------------
        for b in self.buildings:
            if not camera.is_point_in_view(b.rect.centerx, b.rect.centery, margin=max(b.rect.width, b.rect.height) + 120):
                continue

            # Drop Shadow for 3D Top-Down Depth
            shadow_offset = 12 + b.height_tier * 6
            sx, sy = camera.world_to_screen(b.rect.x, b.rect.y)
            shadow_rect = pygame.Rect(sx + shadow_offset, sy + shadow_offset, b.rect.width, b.rect.height)
            shadow_surf = pygame.Surface((b.rect.width, b.rect.height), pygame.SRCALPHA)
            shadow_surf.fill(config.COLOR_BUILDING_SHADOW)
            surface.blit(shadow_surf, (sx + shadow_offset, sy + shadow_offset))

            # Building Base Facade
            b_screen_rect = pygame.Rect(sx, sy, b.rect.width, b.rect.height)
            pygame.draw.rect(surface, config.COLOR_BUILDING_FACADE, b_screen_rect)

            # Building Rooftop Surface
            parapet = 6
            roof_rect = pygame.Rect(sx + parapet, sy + parapet, b.rect.width - parapet * 2, b.rect.height - parapet * 2)
            pygame.draw.rect(surface, b.roof_color, roof_rect)
            pygame.draw.rect(surface, (60, 70, 85), roof_rect, 1)

            # Neon Trim / Architectural Accent
            if b.has_neon_trim:
                pygame.draw.rect(surface, b.accent_color, b_screen_rect, 2)

            # Rooftop Equipment Details
            rx, ry, rw, rh = roof_rect.x, roof_rect.y, roof_rect.width, roof_rect.height

            if b.roof_style == "helipad" and rw > 100 and rh > 100:
                # Helipad circle and "H"
                hc_x, hc_y = rx + rw // 2, ry + rh // 2
                pygame.draw.circle(surface, (230, 200, 40), (hc_x, hc_y), 32, 3)
                pygame.draw.line(surface, (230, 200, 40), (hc_x - 14, hc_y - 18), (hc_x - 14, hc_y + 18), 4)
                pygame.draw.line(surface, (230, 200, 40), (hc_x + 14, hc_y - 18), (hc_x + 14, hc_y + 18), 4)
                pygame.draw.line(surface, (230, 200, 40), (hc_x - 14, hc_y), (hc_x + 14, hc_y), 4)

            elif b.roof_style == "solar":
                # Solar Panel Grid
                panel_w, panel_h = 24, 16
                for px in range(rx + 12, rx + rw - panel_w - 6, panel_w + 6):
                    for py in range(ry + 12, ry + rh - panel_h - 6, panel_h + 6):
                        p_rect = pygame.Rect(px, py, panel_w, panel_h)
                        pygame.draw.rect(surface, (20, 60, 110), p_rect)
                        pygame.draw.rect(surface, (60, 120, 190), p_rect, 1)

            elif b.roof_style == "hvac":
                # HVAC Chiller Units
                for i, (hx, hy) in enumerate([(rx + 16, ry + 16), (rx + rw - 48, ry + 16), (rx + 24, ry + rh - 48)]):
                    h_rect = pygame.Rect(hx, hy, 32, 26)
                    pygame.draw.rect(surface, (70, 78, 90), h_rect)
                    pygame.draw.rect(surface, (95, 105, 120), h_rect, 1)
                    # Chiller Fan
                    pygame.draw.circle(surface, (45, 50, 60), (hx + 16, hy + 13), 8)

            elif b.roof_style == "skylight":
                # Skylight glass pyramid
                sk_rect = pygame.Rect(rx + rw // 4, ry + rh // 4, rw // 2, rh // 2)
                pygame.draw.rect(surface, (30, 90, 140), sk_rect)
                pygame.draw.rect(surface, (100, 180, 240), sk_rect, 2)
                pygame.draw.line(surface, (100, 180, 240), (sk_rect.left, sk_rect.top), (sk_rect.right, sk_rect.bottom), 1)
                pygame.draw.line(surface, (100, 180, 240), (sk_rect.left, sk_rect.bottom), (sk_rect.right, sk_rect.top), 1)

            else:
                # Communication Antenna Mast
                ax, ay = rx + rw // 2, ry + rh // 2
                pygame.draw.circle(surface, (150, 160, 170), (ax, ay), 6)
                pygame.draw.line(surface, (200, 210, 220), (ax, ay), (ax, ay - 14), 2)
                # Blinking Aviation Warning Light
                pulse = (pygame.time.get_ticks() // 500) % 2 == 0
                if pulse:
                    pygame.draw.circle(surface, (255, 40, 40), (ax, ay - 14), 3)

        # -------------------------------------------------------------
        # 8. Sidewalk Trees & Planters
        # -------------------------------------------------------------
        for tx, ty, rad in self.sidewalk_trees:
            if camera.is_point_in_view(tx, ty, margin=50):
                sx, sy = camera.world_to_screen(tx, ty)
                # Planter Box (square stone border)
                p_box = pygame.Rect(sx - rad - 2, sy - rad - 2, (rad + 2) * 2, (rad + 2) * 2)
                pygame.draw.rect(surface, (70, 75, 85), p_box)
                pygame.draw.rect(surface, (35, 40, 45), p_box, 1)
                # Tree Foliage
                pygame.draw.circle(surface, (30, 75, 45), (sx, sy), rad)
                pygame.draw.circle(surface, (45, 105, 60), (sx - 2, sy - 2), rad - 3)

        # -------------------------------------------------------------
        # 9. Street Lamps & Illumination Cones
        # -------------------------------------------------------------
        for lx, ly, rot in self.street_lamps:
            if camera.is_point_in_view(lx, ly, margin=80):
                sx, sy = camera.world_to_screen(lx, ly)
                
                # Ambient Light Glow on Pavement
                glow_surf = pygame.Surface((70, 70), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, config.COLOR_STREET_LAMP_GLOW, (35, 35), 32)
                surface.blit(glow_surf, (sx - 35, sy - 35), special_flags=pygame.BLEND_ADD)

                # Lamp Post Base & Fixture
                pygame.draw.circle(surface, (40, 45, 55), (sx, sy), 5)
                pygame.draw.circle(surface, (255, 245, 200), (sx, sy), 3)

        # -------------------------------------------------------------
        # 10. Traffic Light Signals at Corners
        # -------------------------------------------------------------
        for tl in self.traffic_lights:
            lx, ly = tl["pos"]
            if camera.is_point_in_view(lx, ly, margin=60):
                sx, sy = camera.world_to_screen(lx, ly)
                
                # Signal Housing Box
                sh_w, sh_h = 10, 18
                sh_rect = pygame.Rect(sx - sh_w // 2, sy - sh_h // 2, sh_w, sh_h)
                pygame.draw.rect(surface, (20, 22, 26), sh_rect, border_radius=2)
                pygame.draw.rect(surface, (60, 65, 75), sh_rect, 1, border_radius=2)

                # Signal Lenses (Red, Yellow, Green)
                pygame.draw.circle(surface, config.COLOR_TRAFFIC_LIGHT_RED, (sx, sy - 5), 2)
                pygame.draw.circle(surface, config.COLOR_TRAFFIC_LIGHT_AMBER, (sx, sy), 2)
                pygame.draw.circle(surface, config.COLOR_TRAFFIC_LIGHT_GREEN, (sx, sy + 5), 2)


class Camera:
    """
    Smooth tracking camera with velocity-based lookahead and coordinate projection.
    """
    def __init__(self, x: float = 0.0, y: float = 0.0, screen_w: int = config.SCREEN_WIDTH, screen_h: int = config.SCREEN_HEIGHT):
        self.x = float(x)
        self.y = float(y)
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.lerp_speed = 6.5  # Camera smoothing speed
        self.lookahead_weight = 0.45  # Pixels of forward lookahead per unit velocity

    def update(self, dt: float, target_x: float, target_y: float, target_vx: float, target_vy: float):
        """Smoothly interpolates camera position towards target with forward lookahead."""
        desired_x = target_x + (target_vx * self.lookahead_weight)
        desired_y = target_y + (target_vy * self.lookahead_weight)

        factor = 1.0 - math.exp(-self.lerp_speed * dt)
        self.x += (desired_x - self.x) * factor
        self.y += (desired_y - self.y) * factor

    def world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        """Converts world coordinate (wx, wy) to screen viewport (sx, sy)."""
        sx = int(wx - self.x + (self.screen_w / 2.0))
        sy = int(wy - self.y + (self.screen_h / 2.0))
        return (sx, sy)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        """Converts screen pixel (sx, sy) to world coordinate (wx, wy)."""
        wx = sx - (self.screen_w / 2.0) + self.x
        wy = sy - (self.screen_h / 2.0) + self.y
        return (wx, wy)

    def is_point_in_view(self, wx: float, wy: float, margin: float = 100) -> bool:
        """Culling test: checks if world coordinate is within the visible viewport."""
        sx, sy = self.world_to_screen(wx, wy)
        return (-margin <= sx <= self.screen_w + margin) and (-margin <= sy <= self.screen_h + margin)
