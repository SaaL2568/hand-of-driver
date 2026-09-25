"""Configuration settings for the Pygame Car Simulator."""
import math

# Window & Display
WINDOW_TITLE = "Hand-Gesture Vehicle Simulator (Part B)"
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Networking
DEFAULT_UDP_IP = "0.0.0.0"
DEFAULT_UDP_PORT = 5005
PACKET_TIMEOUT_SEC = 0.5  # Time before flagging packet stream as lost/inactive
SOCKET_BUFFER_SIZE = 4096

# Physics & Vehicle Parameters
CAR_WIDTH = 34           # pixels (approx 1.8m scale)
CAR_LENGTH = 70          # pixels (approx 4.2m scale)
WHEEL_BASE = 48          # distance between axles in pixels

MAX_SPEED_FORWARD = 850.0   # pixels / sec (~ 120 km/h in game units)
MAX_SPEED_REVERSE = -250.0  # pixels / sec
ACCELERATION_RATE = 520.0   # pixels / sec^2
BRAKING_FORCE = 750.0       # pixels / sec^2
PANIC_BRAKE_FORCE = 1600.0  # pixels / sec^2 (rapid emergency stop)
NATURAL_DECEL = 90.0        # rolling resistance / friction
AIR_DRAG_COEFF = 0.0018     # quadratic aerodynamic drag

MAX_STEERING_ANGLE = math.radians(20)  # 20 degrees maximum wheel turn
STEERING_SPEED = math.radians(120)     # steering responsiveness rad/sec
HIGH_SPEED_STEER_SCALE = 0.4           # fraction of steering lock left at top speed
HIGH_SPEED_STEER_RATE_SCALE = 0.6      # fraction of wheel turn rate left at top speed
DRIFT_FACTOR = 0.94                    # lateral grip traction (1.0 = on rails, <0.95 = allows drift)
OFF_ROAD_SPEED_LIMIT = 220.0           # max speed allowed when tires are off asphalt
OFF_ROAD_FRICTION_MULT = 3.2           # extra drag on grass

# Colors (Urban City Night / Cyber Metropolitan Theme)
COLOR_BG = (18, 22, 28)
COLOR_CITY_GROUND = (24, 28, 36)
COLOR_CITY_GROUND_ACCENT = (28, 33, 42)
COLOR_GRASS = COLOR_CITY_GROUND
COLOR_GRASS_ACCENT = COLOR_CITY_GROUND_ACCENT

# City Road & Sidewalk Colors
COLOR_ROAD = (36, 40, 48)
COLOR_ROAD_SHOULDER = (90, 95, 105)
COLOR_SIDEWALK = (55, 60, 72)
COLOR_SIDEWALK_CURB = (110, 120, 135)
COLOR_ROAD_CURB_RED = (200, 45, 45)
COLOR_ROAD_CURB_WHITE = (230, 230, 230)
COLOR_LANE_MARKING = (255, 255, 255)
COLOR_LANE_MARKING_YELLOW = (245, 190, 35)
COLOR_CROSSWALK = (240, 242, 245)
COLOR_FINISH_LINE = (0, 215, 255)

# City Buildings & Architecture
COLOR_BUILDING_SHADOW = (10, 12, 16, 160)
COLOR_BUILDING_FACADE = (30, 35, 45)
COLOR_BUILDING_ROOF_DARK = (42, 48, 60)
COLOR_BUILDING_ROOF_LIGHT = (52, 60, 75)
COLOR_BUILDING_ROOF_GLASS = (35, 55, 75)
COLOR_BUILDING_ACCENT_CYAN = (0, 195, 255)
COLOR_BUILDING_ACCENT_AMBER = (255, 170, 30)
COLOR_TRAFFIC_LIGHT_RED = (255, 45, 45)
COLOR_TRAFFIC_LIGHT_AMBER = (255, 180, 25)
COLOR_TRAFFIC_LIGHT_GREEN = (40, 225, 120)
COLOR_STREET_LAMP_GLOW = (255, 240, 180, 25)

# Car Colors
COLOR_CAR_BODY = (0, 180, 255)       # Cyber Cyan
COLOR_CAR_ACCENT = (10, 30, 45)
COLOR_CAR_ROOF = (15, 25, 35)
COLOR_CAR_GLASS = (120, 200, 240)
COLOR_CAR_HEADLIGHT = (255, 255, 210)
COLOR_CAR_BRAKELIGHT = (255, 30, 30)
COLOR_CAR_TIRE = (20, 20, 20)
COLOR_SKID_MARK = (20, 20, 20, 140)

# HUD Colors
COLOR_HUD_BG = (15, 20, 28, 210)
COLOR_HUD_BORDER = (45, 60, 80)
COLOR_HUD_TEXT = (235, 240, 245)
COLOR_HUD_MUTED = (130, 145, 165)
COLOR_HUD_ACCENT = (0, 215, 255)
COLOR_HUD_THROTTLE = (50, 220, 120)
COLOR_HUD_BRAKE = (255, 70, 70)
COLOR_HUD_PANIC = (255, 30, 30)
COLOR_HUD_CONNECTED = (40, 210, 110)
COLOR_HUD_WAITING = (255, 175, 40)
COLOR_HUD_OFFLINE = (230, 60, 60)

# Keybindings
KEY_TOGGLE_MODE = "TAB"      # Toggle between UDP network and manual keyboard override
KEY_PANIC_STOP = "P"         # Emergency panic brake
KEY_RESET_CAR = "R"          # Reset car position to start
KEY_TOGGLE_HELP = "H"        # Show / hide controls helper overlay
KEY_TOGGLE_TRAILS = "T"       # Toggle tire skid marks
KEY_TOGGLE_MINIMAP = "M"     # Toggle minimap
