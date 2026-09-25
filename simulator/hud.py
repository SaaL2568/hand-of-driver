"""HUD, Telemetry Gauges, Minimap, and Diagnostics Dashboard Overlay."""
import math
import pygame
from typing import Dict, Any, Optional
import config
from physics import CarPhysics
from world import Track


class HUD:
    """
    Renders a comprehensive real-time telemetry dashboard with glassmorphic cards,
    speedometer, pedal bars, steering angle dial, network status, and minimap.
    """
    def __init__(self, screen_w: int = config.SCREEN_WIDTH, screen_h: int = config.SCREEN_HEIGHT):
        self.screen_w = screen_w
        self.screen_h = screen_h
        
        # Initialize Fonts
        pygame.font.init()
        self.font_title = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 24, bold=True)
        self.font_main = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 16, bold=True)
        self.font_small = pygame.font.SysFont("Consolas, monospace", 13)
        self.font_large = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 42, bold=True)

        self.show_help = False
        self.show_minimap = True
        self.show_diagnostics = True

    def render(
        self,
        surface: pygame.Surface,
        physics: CarPhysics,
        track: Track,
        net_stats: Dict[str, Any],
        control_mode: str,          # "NETWORK" or "KEYBOARD"
        steer_input: float,         # -1.0 to 1.0
        throttle_input: float,      # 0.0 to 1.0
        brake_input: float,         # 0.0 to 1.0
        panic_input: bool,
        reverse_input: float = 0.0,
        fps: float = 60.0,
        horn_input: bool = False,
        gear_select: Optional[str] = None,   # "D"/"R" from gesture gear, None in keyboard mode
        gesture_label: str = "",
    ):
        """Renders all HUD components on top of the simulation surface."""
        # 1. Network / Input Status Card (Top Left)
        self._render_network_card(surface, net_stats, control_mode, fps, gesture_label)

        # 2. Controls & Pedals Card (Bottom Left)
        self._render_controls_card(surface, steer_input, throttle_input, brake_input, panic_input, reverse_input, physics)

        # 3. Speedometer & Velocity Gauge (Bottom Right)
        self._render_speedometer(surface, physics, gear_select)

        # 4. Emergency Panic Alert Banner (Top Center if active)
        if physics.is_panic_stopped or panic_input:
            self._render_panic_banner(surface)
        elif physics.is_offroad:
            self._render_offroad_banner(surface)
        if horn_input:
            self._render_horn_badge(surface)

        # 5. Minimap Radar (Top Right)
        if self.show_minimap:
            self._render_minimap(surface, physics, track)

        # 6. Controls Help Overlay (if toggled)
        if self.show_help:
            self._render_help_overlay(surface)
        else:
            # Subtle hint in bottom right
            hint_txt = self.font_small.render("[H] Help | [W] Gas | [S] Reverse | [Space] Stop | [TAB] Mode", True, config.COLOR_HUD_MUTED)
            surface.blit(hint_txt, (self.screen_w - hint_txt.get_width() - 20, self.screen_h - 24))

    def _render_card_bg(self, surface: pygame.Surface, rect: pygame.Rect):
        """Draws a sleek semi-transparent glass card with border."""
        card_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        card_surf.fill(config.COLOR_HUD_BG)
        surface.blit(card_surf, (rect.x, rect.y))
        pygame.draw.rect(surface, config.COLOR_HUD_BORDER, rect, 1, border_radius=8)

    def _render_network_card(self, surface: pygame.Surface, net: Dict[str, Any], mode: str, fps: float,
                             gesture_label: str = ""):
        """Renders UDP connection health, packet frequencies, and mode."""
        w, h = 330, 162
        x, y = 20, 20
        self._render_card_bg(surface, pygame.Rect(x, y, w, h))

        # Status Dot & Title
        is_connected = net.get("is_connected", False)
        if mode == "KEYBOARD":
            status_col = config.COLOR_HUD_WAITING
            status_text = "MANUAL OVERRIDE (KEYBOARD)"
        elif is_connected:
            status_col = config.COLOR_HUD_CONNECTED
            status_text = f"GESTURE CONNECTED [{net.get('packet_rate_hz', 0)} Hz]"
        else:
            status_col = config.COLOR_HUD_OFFLINE
            status_text = "WAITING FOR UDP (KEYBOARD READY)"

        pygame.draw.circle(surface, status_col, (x + 18, y + 22), 6)
        title_surf = self.font_main.render(status_text, True, config.COLOR_HUD_TEXT)
        surface.blit(title_surf, (x + 32, y + 13))

        # Telemetry Metrics
        lines = [
            f"Active Mode  : {mode} (Press TAB to switch)",
            f"UDP Endpoint : {net.get('host', '0.0.0.0')}:{net.get('port', 5005)}",
            f"Packets Rcvd : {net.get('packet_count', 0)} (Malformed: {net.get('malformed_count', 0)})",
            f"Packet Age   : {net.get('packet_age_sec', 0.0):.2f}s | App FPS: {int(fps)}",
            f"YOLO Gesture : {gesture_label if gesture_label not in ('', '-') else '--'}",
        ]

        for i, line in enumerate(lines):
            line_surf = self.font_small.render(line, True, config.COLOR_HUD_MUTED)
            surface.blit(line_surf, (x + 16, y + 44 + i * 21))

    def _render_controls_card(
        self,
        surface: pygame.Surface,
        steer: float,
        throttle: float,
        brake: float,
        panic: bool,
        reverse: float,
        physics: CarPhysics
    ):
        """Renders steering wheel rotation dial and throttle/reverse/brake meter bars."""
        w, h = 330, 160
        x, y = 20, self.screen_h - h - 20
        self._render_card_bg(surface, pygame.Rect(x, y, w, h))

        # Card Title
        hdr = self.font_main.render("VEHICLE INPUTS", True, config.COLOR_HUD_ACCENT)
        surface.blit(hdr, (x + 16, y + 12))

        # 1. Steering Dial
        dial_center = (x + 65, y + 90)
        dial_radius = 42
        pygame.draw.circle(surface, (30, 40, 55), dial_center, dial_radius)
        pygame.draw.circle(surface, config.COLOR_HUD_BORDER, dial_center, dial_radius, 2)
        
        # Steering Wheel Spokes / Needle
        curr_steer_deg = math.degrees(physics.steer_angle)
        steer_rad = math.radians(curr_steer_deg - 90)
        nx = dial_center[0] + math.cos(steer_rad) * (dial_radius - 6)
        ny = dial_center[1] + math.sin(steer_rad) * (dial_radius - 6)
        pygame.draw.line(surface, config.COLOR_HUD_ACCENT, dial_center, (nx, ny), 4)
        pygame.draw.circle(surface, config.COLOR_HUD_ACCENT, dial_center, 5)

        steer_lbl = self.font_small.render(f"STEER: {curr_steer_deg:+.1f}°", True, config.COLOR_HUD_TEXT)
        surface.blit(steer_lbl, (dial_center[0] - steer_lbl.get_width() // 2, y + 138))

        # 2. Forward Throttle / Reverse Bar
        bar_x = x + 140
        bar_w = 160
        bar_h = 16
        
        if reverse > 0:
            t_lbl = self.font_small.render(f"REVERSE: {int(reverse * 100)}%", True, config.COLOR_HUD_WAITING)
            bar_fill_col = config.COLOR_HUD_WAITING
            fill_amount = reverse
        else:
            t_lbl = self.font_small.render(f"GAS [W]: {int(throttle * 100)}%", True, config.COLOR_HUD_THROTTLE)
            bar_fill_col = config.COLOR_HUD_THROTTLE
            fill_amount = throttle

        surface.blit(t_lbl, (bar_x, y + 42))
        
        pygame.draw.rect(surface, (25, 35, 45), (bar_x, y + 60, bar_w, bar_h), border_radius=4)
        if fill_amount > 0:
            fill_w = int(bar_w * fill_amount)
            pygame.draw.rect(surface, bar_fill_col, (bar_x, y + 60, fill_w, bar_h), border_radius=4)
        pygame.draw.rect(surface, config.COLOR_HUD_BORDER, (bar_x, y + 60, bar_w, bar_h), 1, border_radius=4)

        # 3. Brake / Stop Bar (Red)
        b_lbl = self.font_small.render(f"STOP [SPACE]: {int(brake * 100)}%", True, config.COLOR_HUD_BRAKE)
        surface.blit(b_lbl, (bar_x, y + 86))
        
        pygame.draw.rect(surface, (25, 35, 45), (bar_x, y + 104, bar_w, bar_h), border_radius=4)
        if brake > 0:
            fill_w = int(bar_w * brake)
            pygame.draw.rect(surface, config.COLOR_HUD_BRAKE, (bar_x, y + 104, fill_w, bar_h), border_radius=4)
        pygame.draw.rect(surface, config.COLOR_HUD_BORDER, (bar_x, y + 104, bar_w, bar_h), 1, border_radius=4)

    def _render_speedometer(self, surface: pygame.Surface, physics: CarPhysics, gear_select: Optional[str] = None):
        """Renders high-visibility digital speedometer and gear status."""
        w, h = 250, 160
        x, y = self.screen_w - w - 20, self.screen_h - h - 20
        self._render_card_bg(surface, pygame.Rect(x, y, w, h))

        # Speed Number
        speed_val = int(round(physics.speed_kmh))
        speed_txt = self.font_large.render(f"{speed_val:03d}", True, config.COLOR_HUD_ACCENT)
        surface.blit(speed_txt, (x + 30, y + 25))

        unit_txt = self.font_main.render("KM/H", True, config.COLOR_HUD_MUTED)
        surface.blit(unit_txt, (x + 130, y + 45))

        # Gear Indicator (P, R, N, D)
        if physics.is_panic_stopped:
            gear = "P"
            gear_col = config.COLOR_HUD_PANIC
        elif physics.is_reversing:
            gear = "R"
            gear_col = config.COLOR_HUD_WAITING
        elif abs(physics.velocity) < 2.0:
            gear = "N"
            gear_col = config.COLOR_HUD_MUTED
        else:
            gear = "D"
            gear_col = config.COLOR_HUD_CONNECTED

        gear_badge = self.font_main.render(f"GEAR: [{gear}]", True, gear_col)
        surface.blit(gear_badge, (x + 30, y + 90))

        # Gesture gear selector (peace sign toggles D <-> R)
        if gear_select:
            sel_col = config.COLOR_HUD_WAITING if gear_select == "R" else config.COLOR_HUD_CONNECTED
            sel = self.font_main.render(f"SELECT: {gear_select}", True, sel_col)
            surface.blit(sel, (x + 140, y + 90))

        # Heading & Slip info
        info_txt = self.font_small.render(f"HDG: {physics.heading_deg:.0f}° | SLIP: {int(physics.slip_ratio*100)}%", True, config.COLOR_HUD_MUTED)
        surface.blit(info_txt, (x + 30, y + 120))

    def _render_horn_badge(self, surface: pygame.Surface):
        """Pulsing HORN badge under the top banner area while the horn is held."""
        bw, bh = 160, 40
        bx, by = (self.screen_w - bw) // 2, 86
        pulse = (pygame.time.get_ticks() // 150) % 2 == 0
        badge = pygame.Surface((bw, bh), pygame.SRCALPHA)
        badge.fill((255, 200, 0, 230) if pulse else (200, 150, 0, 200))
        surface.blit(badge, (bx, by))
        pygame.draw.rect(surface, (255, 255, 255), (bx, by, bw, bh), 2, border_radius=6)
        msg = self.font_title.render("HORN", True, (20, 20, 20))
        surface.blit(msg, (bx + (bw - msg.get_width()) // 2, by + (bh - msg.get_height()) // 2))

    def _render_panic_banner(self, surface: pygame.Surface):
        """Flashing bright warning banner when emergency stop is triggered."""
        banner_w, banner_h = 440, 52
        bx = (self.screen_w - banner_w) // 2
        by = 24

        # Pulse effect using ticks
        pulse = (pygame.time.get_ticks() // 250) % 2 == 0
        bg_col = (220, 20, 20, 230) if pulse else (140, 10, 10, 200)

        banner_surf = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
        banner_surf.fill(bg_col)
        surface.blit(banner_surf, (bx, by))
        pygame.draw.rect(surface, (255, 255, 255), (bx, by, banner_w, banner_h), 2, border_radius=6)

        msg = self.font_title.render("!! PANIC STOP ENGAGED !!", True, (255, 255, 255))
        surface.blit(msg, (bx + (banner_w - msg.get_width()) // 2, by + 12))

    def _render_offroad_banner(self, surface: pygame.Surface):
        """Alert indicator when driving off-road or on sidewalk."""
        banner_w, banner_h = 300, 36
        bx = (self.screen_w - banner_w) // 2
        by = 24
        
        banner_surf = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
        banner_surf.fill((180, 110, 20, 210))
        surface.blit(banner_surf, (bx, by))
        pygame.draw.rect(surface, (255, 200, 80), (bx, by, banner_w, banner_h), 1, border_radius=6)
        
        msg = self.font_main.render("OFF ROAD - REDUCED TRACTION", True, (255, 255, 255))
        surface.blit(msg, (bx + (banner_w - msg.get_width()) // 2, by + 8))

    def _render_minimap(self, surface: pygame.Surface, physics: CarPhysics, track: Track):
        """Draws top-right city grid radar minimap with player blip."""
        size = 180
        x, y = self.screen_w - size - 20, 20
        self._render_card_bg(surface, pygame.Rect(x, y, size, size))

        # Title
        hdr = self.font_small.render("CITY RADAR", True, config.COLOR_HUD_ACCENT)
        surface.blit(hdr, (x + 12, y + 8))

        # Calculate bounding box of track
        xs = [p[0] for p in track.centerline]
        ys = [p[1] for p in track.centerline]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)
        padding = 18
        inner_w = size - padding * 2
        inner_h = size - padding * 2 - 12

        scale = min(inner_w / span_x, inner_h / span_y)
        offset_x = x + padding + (inner_w - span_x * scale) / 2.0
        offset_y = y + padding + 12 + (inner_h - span_y * scale) / 2.0

        # Draw minimap streets
        mini_pts = []
        for cx, cy in track.centerline[::6]:
            mx = offset_x + (cx - min_x) * scale
            my = offset_y + (cy - min_y) * scale
            mini_pts.append((int(mx), int(my)))

        if len(mini_pts) > 2:
            pygame.draw.lines(surface, (65, 95, 135), True, mini_pts, 3)

        # Draw Corner Intersection Nodes
        for cx, cy in getattr(track, 'corner_points', []):
            mx = int(offset_x + (cx - min_x) * scale)
            my = int(offset_y + (cy - min_y) * scale)
            pygame.draw.circle(surface, (100, 160, 230), (mx, my), 2)

        # Draw Player Blip
        car_mx = int(offset_x + (physics.x - min_x) * scale)
        car_my = int(offset_y + (physics.y - min_y) * scale)
        
        # Clamp to minimap bounds
        car_mx = max(x + 4, min(x + size - 4, car_mx))
        car_my = max(y + 4, min(y + size - 4, car_my))

        pygame.draw.circle(surface, (255, 60, 60), (car_mx, car_my), 4)
        
        # Player heading tick
        hx = car_mx + int(math.cos(physics.heading) * 9)
        hy = car_my + int(math.sin(physics.heading) * 9)
        pygame.draw.line(surface, (255, 255, 255), (car_mx, car_my), (hx, hy), 2)

    def _render_help_overlay(self, surface: pygame.Surface):
        """Modal dialog showing keybindings and control instructions."""
        modal_w, modal_h = 620, 360
        mx = (self.screen_w - modal_w) // 2
        my = (self.screen_h - modal_h) // 2

        # Dim background
        dim_surf = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 170))
        surface.blit(dim_surf, (0, 0))

        # Modal Box
        modal_rect = pygame.Rect(mx, my, modal_w, modal_h)
        self._render_card_bg(surface, modal_rect)

        # Title
        t = self.font_title.render("SIMULATOR CONTROLS & USAGE", True, config.COLOR_HUD_ACCENT)
        surface.blit(t, (mx + 24, my + 20))

        controls_list = [
            ("W / Up Arrow", "Apply Throttle (Forward Gas)"),
            ("S / Down Arrow", "Reverse Gear (Drive Backward)"),
            ("Spacebar", "Brake / Stop Vehicle"),
            ("A / Left Arrow", "Steer Left"),
            ("D / Right Arrow", "Steer Right"),
            ("P", "Trigger Panic Stop (Emergency Brake)"),
            ("TAB", "Toggle Input Source (Network UDP vs Keyboard Override)"),
            ("R", "Reset Vehicle to Start Position"),
            ("T", "Toggle Tire Skid Trails"),
            ("M", "Toggle Minimap"),
            ("H", "Close this Help Dialog"),
        ]

        for i, (key, desc) in enumerate(controls_list):
            row_y = my + 65 + i * 24
            k_surf = self.font_small.render(f"[{key}]", True, config.COLOR_HUD_TEXT)
            d_surf = self.font_small.render(desc, True, config.COLOR_HUD_MUTED)
            surface.blit(k_surf, (mx + 30, row_y))
            surface.blit(d_surf, (mx + 200, row_y))
