"""Per-user calibration for the MediaPipe thumb controller.

A short guided routine records each user's comfortable hand poses:

  NEUTRAL -> thumb up, hand relaxed in the middle  (straight + coasting)
  LEFT    -> thumb tilted fully left               (full left lock)
  RIGHT   -> thumb tilted fully right              (full right lock)
  UP      -> hand raised                           (full throttle)
  DOWN    -> hand lowered                          (full brake)

From these it derives a CalibrationProfile: the neutral thumb angle (people rarely
hold their thumb perfectly vertical), separate left/right steering ranges, pedal
centre and throttle/brake ranges, and dead zones sized from the user's own hand
tremor. Profiles are saved as JSON so each user only calibrates once.
"""
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

PROFILE_DIR = Path(__file__).resolve().parent / "calibration_profiles"


@dataclass
class CalibrationProfile:
    """Mapping parameters for one user. Defaults = uncalibrated behaviour."""
    user: str = "default"
    neutral_angle: float = 0.0     # thumb tilt (deg) that means "straight"
    steer_left_deg: float = 65.0   # tilt from neutral that gives full left lock
    steer_right_deg: float = 65.0  # tilt from neutral that gives full right lock
    steer_dead_deg: float = 8.0    # tilt ignored around neutral
    pedal_center: float = 0.5      # palm height (0 top .. 1 bottom) for coasting
    pedal_dead_zone: float = 0.16  # coasting band width
    throttle_range: float = 0.28   # dead-zone edge -> full throttle distance
    brake_range: float = 0.28      # dead-zone edge -> full brake distance
    calibrated: bool = False
    created: str = ""
    notes: List[str] = field(default_factory=list)

    @staticmethod
    def path_for(user: str) -> Path:
        safe = "".join(ch for ch in user if ch.isalnum() or ch in "-_") or "default"
        return PROFILE_DIR / f"{safe}.json"

    def save(self) -> Path:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        path = self.path_for(self.user)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, user: str) -> Optional["CalibrationProfile"]:
        path = cls.path_for(user)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        except (OSError, ValueError, TypeError) as err:
            print(f"[Calibration] Could not read {path}: {err}")
            return None

    def summary(self) -> str:
        return (f"neutral {self.neutral_angle:+.1f} deg | lock L {self.steer_left_deg:.0f} / "
                f"R {self.steer_right_deg:.0f} deg | dead {self.steer_dead_deg:.1f} deg | "
                f"pedal centre {self.pedal_center:.2f} dz {self.pedal_dead_zone:.2f} "
                f"thr {self.throttle_range:.2f} brk {self.brake_range:.2f}")


@dataclass
class Stage:
    key: str
    title: str
    instruction: str
    duration: float = 2.5


STAGES = [
    Stage("NEUTRAL", "1/5  NEUTRAL", "Thumb UP, hand relaxed in the MIDDLE. Hold still."),
    Stage("LEFT", "2/5  FULL LEFT", "Tilt your thumb as far LEFT as is comfortable."),
    Stage("RIGHT", "3/5  FULL RIGHT", "Tilt your thumb as far RIGHT as is comfortable."),
    Stage("UP", "4/5  FULL THROTTLE", "Thumb up, RAISE your hand as high as is comfortable."),
    Stage("DOWN", "5/5  FULL BRAKE", "Thumb up, LOWER your hand as low as is comfortable."),
]

PREP_SEC = 1.5          # time to get into position before recording each stage
SETTLE_FRACTION = 0.3   # ignore the first 30% of each recording window
FULL_SCALE_USE = 0.85   # full lock/pedal is reached at 85% of the recorded extreme


class CalibrationSession:
    """Timed state machine. Feed it hand samples each frame; it builds a profile."""

    def __init__(self, user: str, defaults: Optional[CalibrationProfile] = None):
        self.user = user
        self.defaults = defaults or CalibrationProfile(user=user)
        self.stage_idx = 0
        self.stage_start = None
        self.samples: Dict[str, List[tuple]] = {s.key: [] for s in STAGES}
        self.done = False
        self.retry = False
        self.profile: Optional[CalibrationProfile] = None

    @property
    def stage(self) -> Optional[Stage]:
        return STAGES[self.stage_idx] if self.stage_idx < len(STAGES) else None

    def status(self, now: float) -> dict:
        """What the UI should show right now."""
        stage = self.stage
        if stage is None:
            return {"done": True}
        elapsed = 0.0 if self.stage_start is None else now - self.stage_start
        recording = elapsed >= PREP_SEC
        if recording:
            progress = min(1.0, (elapsed - PREP_SEC) / stage.duration)
        else:
            progress = 0.0
        return {
            "done": False,
            "title": stage.title,
            "instruction": stage.instruction,
            "recording": recording,
            "countdown": max(0.0, PREP_SEC - elapsed),
            "progress": progress,
            "samples": len(self.samples[stage.key]),
            "retry": self.retry,
        }

    def feed(self, now: float, angle: Optional[float], palm_y: Optional[float]):
        """Record one frame. angle/palm_y are None when no hand is visible."""
        stage = self.stage
        if stage is None:
            return
        if self.stage_start is None:
            self.stage_start = now
        elapsed = now - self.stage_start
        if elapsed < PREP_SEC:
            return
        if angle is not None and palm_y is not None:
            self.samples[stage.key].append((elapsed - PREP_SEC, angle, palm_y))
        if elapsed >= PREP_SEC + stage.duration:
            if len(self._settled(stage.key)) > 0:
                self.stage_idx += 1
                self.retry = False
            else:
                # Not enough hand frames: repeat this stage instead of guessing
                self.samples[stage.key] = []
                self.retry = True
            self.stage_start = now
            if self.stage is None:
                self.profile = self.compute()
                self.done = True

    def _settled(self, key: str) -> np.ndarray:
        """Samples after the settle period, as array of (angle, palm_y)."""
        rows = self.samples[key]
        if not rows:
            return np.empty((0, 2))
        cutoff = STAGES[[s.key for s in STAGES].index(key)].duration * SETTLE_FRACTION
        kept = [(a, y) for t, a, y in rows if t >= cutoff]
        return np.array(kept) if len(kept) >= 5 else np.empty((0, 2))

    def compute(self) -> CalibrationProfile:
        """Turn recorded samples into a profile, falling back to defaults per axis."""
        d = self.defaults
        p = CalibrationProfile(user=self.user, calibrated=True,
                               created=time.strftime("%Y-%m-%d %H:%M:%S"))
        neu, left, right, up, down = (self._settled(s.key) for s in STAGES)

        # --- Steering ---
        p.neutral_angle = float(np.median(neu[:, 0]))
        # Dead zone scales with the user's own tremor, within sensible limits
        p.steer_dead_deg = float(np.clip(3.0 * np.std(neu[:, 0]), 4.0, 15.0))
        left_span = p.neutral_angle - float(np.median(left[:, 0]))
        right_span = float(np.median(right[:, 0])) - p.neutral_angle
        min_span = p.steer_dead_deg + 10.0
        if left_span >= min_span:
            p.steer_left_deg = FULL_SCALE_USE * left_span
        else:
            p.steer_left_deg = d.steer_left_deg
            p.notes.append(f"left tilt too small ({left_span:.0f} deg) - using default")
        if right_span >= min_span:
            p.steer_right_deg = FULL_SCALE_USE * right_span
        else:
            p.steer_right_deg = d.steer_right_deg
            p.notes.append(f"right tilt too small ({right_span:.0f} deg) - using default")

        # --- Pedals ---
        p.pedal_center = float(np.median(neu[:, 1]))
        p.pedal_dead_zone = float(np.clip(6.0 * np.std(neu[:, 1]), 0.08, 0.2))
        half_dz = p.pedal_dead_zone / 2.0
        up_span = p.pedal_center - float(np.median(up[:, 1])) - half_dz
        down_span = float(np.median(down[:, 1])) - p.pedal_center - half_dz
        if up_span >= 0.08:
            p.throttle_range = FULL_SCALE_USE * up_span
        else:
            p.throttle_range = d.throttle_range
            p.notes.append(f"raise range too small ({up_span:.2f}) - using default")
        if down_span >= 0.08:
            p.brake_range = FULL_SCALE_USE * down_span
        else:
            p.brake_range = d.brake_range
            p.notes.append(f"lower range too small ({down_span:.2f}) - using default")

        return p
