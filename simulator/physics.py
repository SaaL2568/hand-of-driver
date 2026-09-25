"""Vehicle Physics and Kinematic Bicycle Dynamics Model."""
import math
from typing import Tuple
import config


class CarPhysics:
    """
    Simulates realistic 2D vehicle physics using a kinematic bicycle model
    with longitudinal acceleration, rolling resistance, aerodynamic drag,
    and lateral tire friction.
    """
    def __init__(self, x: float = 0.0, y: float = 0.0, heading: float = 0.0):
        # Position and Orientation
        self.x = float(x)
        self.y = float(y)
        self.heading = float(heading)  # Angle in radians (0 = facing right, pi/2 = facing down)
        
        # Motion State
        self.velocity = 0.0            # Signed scalar speed (pixels/sec)
        self.acceleration = 0.0        # Current acceleration (pixels/sec^2)
        self.steer_angle = 0.0         # Current physical wheel steer angle in radians
        self.angular_velocity = 0.0    # Rotation speed (rad/sec)
        self.slip_ratio = 0.0          # Metric for tire slip / skid detection
        
        # Operational Flags
        self.is_braking = False
        self.is_reversing = False
        self.is_panic_stopped = False
        self.is_offroad = False
        self.is_skidding = False

    def reset(self, x: float, y: float, heading: float = 0.0):
        """Resets the car state to the given start position and orientation."""
        self.x = float(x)
        self.y = float(y)
        self.heading = float(heading)
        self.velocity = 0.0
        self.acceleration = 0.0
        self.steer_angle = 0.0
        self.angular_velocity = 0.0
        self.slip_ratio = 0.0
        self.is_braking = False
        self.is_reversing = False
        self.is_panic_stopped = False
        self.is_offroad = False
        self.is_skidding = False

    def update(
        self,
        dt: float,
        target_steer_norm: float,  # -1.0 (left) to 1.0 (right)
        throttle: float,            # 0.0 to 1.0 (forward)
        brake: float,               # 0.0 to 1.0 (stop/brake only)
        panic_stop: bool,           # emergency stop trigger
        reverse: float = 0.0,       # 0.0 to 1.0 (reverse gear)
        is_offroad: bool = False
    ):
        """
        Updates the physics simulation step over time dt (seconds).
        """
        if dt <= 0.0:
            return

        self.is_offroad = is_offroad
        target_steer_norm = max(-1.0, min(1.0, target_steer_norm))
        throttle = max(0.0, min(1.0, throttle))
        brake = max(0.0, min(1.0, brake))
        reverse = max(0.0, min(1.0, reverse))
        
        # Speed-sensitive steering: full lock when slow, reduced lock and slower wheel
        # rate at speed, so steering while accelerating stays controllable.
        speed_ratio = min(1.0, abs(self.velocity) / config.MAX_SPEED_FORWARD)
        lock_scale = 1.0 - (1.0 - config.HIGH_SPEED_STEER_SCALE) * speed_ratio
        rate_scale = 1.0 - (1.0 - config.HIGH_SPEED_STEER_RATE_SCALE) * speed_ratio

        # Map normalized steer [-1, 1] to radians [-MAX_STEERING_ANGLE, MAX_STEERING_ANGLE]
        target_steer_angle = target_steer_norm * config.MAX_STEERING_ANGLE * lock_scale

        # Smooth steering transition (prevent instantaneous snappy wheel turns)
        steer_diff = target_steer_angle - self.steer_angle
        max_steer_change = config.STEERING_SPEED * rate_scale * dt
        if abs(steer_diff) <= max_steer_change:
            self.steer_angle = target_steer_angle
        else:
            self.steer_angle += math.copysign(max_steer_change, steer_diff)

        # -----------------------------------------------------------------
        # 1. Longitudinal Force & Acceleration Calculation
        # -----------------------------------------------------------------
        self.is_panic_stopped = panic_stop
        self.is_braking = brake > 0.05 or panic_stop

        if panic_stop:
            # Panic stop overrides all inputs with maximum emergency brake force
            throttle = 0.0
            reverse = 0.0
            if self.velocity > 0:
                self.acceleration = -config.PANIC_BRAKE_FORCE
            elif self.velocity < 0:
                self.acceleration = config.PANIC_BRAKE_FORCE
            else:
                self.acceleration = 0.0
        else:
            accel_force = 0.0

            # Forward Throttle
            if throttle > 0.0:
                if self.velocity < -5.0:
                    # Throttle acts as brake when moving in reverse
                    accel_force += throttle * config.BRAKING_FORCE
                else:
                    accel_force += throttle * config.ACCELERATION_RATE

            # Dedicated Reverse Gear (S key)
            if reverse > 0.0:
                if self.velocity > 10.0:
                    # Reverse acts as brake when moving forward fast
                    accel_force -= reverse * config.BRAKING_FORCE
                else:
                    # Accelerate backward in reverse
                    accel_force -= reverse * (config.ACCELERATION_RATE * 0.75)
                self.is_reversing = True
            else:
                self.is_reversing = self.velocity < -3.0

            # Dedicated Brake / Stop (Spacebar)
            if brake > 0.0:
                if self.velocity > 0.0:
                    accel_force -= brake * config.BRAKING_FORCE
                elif self.velocity < 0.0:
                    accel_force += brake * config.BRAKING_FORCE
                # If stopped, brake exerts no directional force, keeping car still

            # Passive Resistances (Rolling resistance & Air Drag)
            friction_mult = config.OFF_ROAD_FRICTION_MULT if is_offroad else 1.0
            natural_friction = config.NATURAL_DECEL * friction_mult
            air_drag = config.AIR_DRAG_COEFF * (self.velocity ** 2)

            if abs(self.velocity) > 0.1:
                friction_dir = -1.0 if self.velocity > 0 else 1.0
                accel_force += friction_dir * (natural_friction + air_drag)

            self.acceleration = accel_force

        # -----------------------------------------------------------------
        # 2. Velocity Integration
        # -----------------------------------------------------------------
        prev_velocity = self.velocity
        self.velocity += self.acceleration * dt

        # When braking or coasting, prevent oscillation past zero
        if brake > 0.05 or panic_stop or (throttle == 0.0 and reverse == 0.0):
            if (prev_velocity > 0 and self.velocity <= 0) or (prev_velocity < 0 and self.velocity >= 0):
                self.velocity = 0.0

        # Velocity clamping
        max_fwd = config.OFF_ROAD_SPEED_LIMIT if is_offroad else config.MAX_SPEED_FORWARD
        self.velocity = max(config.MAX_SPEED_REVERSE, min(max_fwd, self.velocity))

        # -----------------------------------------------------------------
        # 3. Angular Kinematics (Bicycle Model)
        # -----------------------------------------------------------------
        # Turning only occurs when vehicle is in motion
        if abs(self.velocity) > 1.0:
            # Kinematic angular velocity: omega = (v / L) * tan(delta)
            # Reverse steering direction if moving in reverse
            direction = 1.0 if self.velocity >= 0 else -1.0
            self.angular_velocity = (self.velocity / config.WHEEL_BASE) * math.tan(self.steer_angle)
            self.heading += self.angular_velocity * dt
            # Keep heading in [-pi, pi] or [0, 2pi]
            self.heading = (self.heading + math.pi) % (2 * math.pi) - math.pi
        else:
            self.angular_velocity = 0.0

        # -----------------------------------------------------------------
        # 4. Position Integration
        # -----------------------------------------------------------------
        forward_dx = math.cos(self.heading) * self.velocity * dt
        forward_dy = math.sin(self.heading) * self.velocity * dt

        self.x += forward_dx
        self.y += forward_dy

        # -----------------------------------------------------------------
        # 5. Slip / Skid detection for visuals and audio
        # -----------------------------------------------------------------
        lateral_accel = abs(self.velocity * self.angular_velocity)
        heavy_brake_skid = (self.velocity > 250.0 and brake > 0.6) or (panic_stop and self.velocity > 150.0)
        high_speed_turn_skid = (lateral_accel > 380.0 and abs(self.velocity) > 280.0)
        
        self.is_skidding = heavy_brake_skid or high_speed_turn_skid
        self.slip_ratio = min(1.0, (lateral_accel / 500.0) + (1.0 if heavy_brake_skid else 0.0))

    @property
    def speed_kmh(self) -> float:
        """Converts internal pixel units to simulated km/h."""
        # Scale: MAX_SPEED_FORWARD (850 px/s) ~= 140 km/h
        return abs(self.velocity) * 0.165

    @property
    def speed_mph(self) -> float:
        return self.speed_kmh * 0.621371

    @property
    def heading_deg(self) -> float:
        """Returns heading in degrees."""
        return math.degrees(self.heading) % 360.0

    def get_corners(self) -> list:
        """
        Returns the 4 world-space corner points (tuples) of the car bounding box.
        Useful for collisions and tire mark emitter locations.
        """
        cos_h = math.cos(self.heading)
        sin_h = math.sin(self.heading)
        
        half_w = config.CAR_WIDTH / 2.0
        half_l = config.CAR_LENGTH / 2.0
        
        # Local offsets: Front-Left, Front-Right, Rear-Right, Rear-Left
        local_pts = [
            (half_l, -half_w),
            (half_l, half_w),
            (-half_l, half_w),
            (-half_l, -half_w)
        ]
        
        world_pts = []
        for lx, ly in local_pts:
            wx = self.x + (lx * cos_h - ly * sin_h)
            wy = self.y + (lx * sin_h + ly * cos_h)
            world_pts.append((wx, wy))
            
        return world_pts
