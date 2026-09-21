import cv2
import mediapipe as mp


# ============================================================
# SETTINGS
# ============================================================

MODEL_PATH = "hand_landmarker.task"

SMOOTHING_ALPHA = 0.15
STABLE_FRAMES = 8


# ============================================================
# MEDIAPIPE SETUP
# ============================================================

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


options = HandLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=MODEL_PATH
    ),
    running_mode=VisionRunningMode.IMAGE,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)


# ============================================================
# CAMERA
# ============================================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not access webcam")
    exit()


# ============================================================
# VARIABLES
# ============================================================

smooth_dx = 0.0
smooth_dy = 0.0

stable_direction = "NONE"
candidate_direction = "NONE"

direction_count = 0


# ============================================================
# START MEDIAPIPE
# ============================================================

with HandLandmarker.create_from_options(options) as landmarker:

    while True:

        ret, frame = cap.read()

        if not ret:
            print("Could not read webcam frame")
            break


        # ====================================================
        # MIRROR CAMERA
        # ====================================================

        frame = cv2.flip(frame, 1)


        # ====================================================
        # MEDIAPIPE INPUT
        # ====================================================

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )


        result = landmarker.detect(mp_image)


        # Default values
        direction = stable_direction
        intensity = 0
        action = "NO ACTION"


        frame_height, frame_width, _ = frame.shape


        # ====================================================
        # HAND DETECTED
        # ====================================================

        if result.hand_landmarks:

            hand = result.hand_landmarks[0]


            # ------------------------------------------------
            # THUMB BASE AND TIP
            # ------------------------------------------------

            thumb_base = hand[2]
            thumb_tip = hand[4]


            base_x = thumb_base.x
            base_y = thumb_base.y

            thumb_x = thumb_tip.x
            thumb_y = thumb_tip.y


            # ------------------------------------------------
            # THUMB ORIENTATION
            # ------------------------------------------------

            dx = thumb_x - base_x
            dy = thumb_y - base_y


            # ------------------------------------------------
            # SMOOTH THUMB MOVEMENT
            # ------------------------------------------------

            smooth_dx = (
                SMOOTHING_ALPHA * dx
                + (1 - SMOOTHING_ALPHA) * smooth_dx
            )

            smooth_dy = (
                SMOOTHING_ALPHA * dy
                + (1 - SMOOTHING_ALPHA) * smooth_dy
            )


            # ------------------------------------------------
            # DIRECTION DETECTION
            # ------------------------------------------------

            horizontal_strength = abs(smooth_dx)
            vertical_strength = abs(smooth_dy)


            # Horizontal gets priority.
            #
            # ↗ → RIGHT
            # → → RIGHT
            # ↘ → RIGHT
            #
            # ↖ → LEFT
            # ← → LEFT
            # ↙ → LEFT

            if horizontal_strength > vertical_strength * 0.45:

                if smooth_dx > 0:
                    raw_direction = "RIGHT"
                else:
                    raw_direction = "LEFT"


            else:

                if smooth_dy < 0:
                    raw_direction = "UP"
                else:
                    raw_direction = "DOWN"


            # ------------------------------------------------
            # DIRECTION STABILIZATION
            # ------------------------------------------------

            if raw_direction == stable_direction:

                candidate_direction = raw_direction
                direction_count = 0

            else:

                if raw_direction == candidate_direction:

                    direction_count += 1

                else:

                    candidate_direction = raw_direction
                    direction_count = 1


                if direction_count >= STABLE_FRAMES:

                    stable_direction = candidate_direction
                    direction_count = 0


            direction = stable_direction


            # =================================================
            # ACTION
            # =================================================

            if direction == "UP":

                action = "ACCELERATE"

            elif direction == "DOWN":

                action = "BRAKE"

            elif direction == "LEFT":

                action = "LEFT TURN"

            elif direction == "RIGHT":

                action = "RIGHT TURN"

            else:

                action = "NO ACTION"


            # =================================================
            # INTENSITY
            #
            # Direction = thumb orientation
            # Intensity = thumb position in full frame
            # =================================================

            if direction == "UP":

                intensity = (1 - thumb_y) * 100

            elif direction == "DOWN":

                intensity = thumb_y * 100

            elif direction == "RIGHT":

                intensity = thumb_x * 100

            elif direction == "LEFT":

                intensity = (1 - thumb_x) * 100

            else:

                intensity = 0


            # Keep intensity between 0 and 100

            intensity = max(
                0,
                min(100, intensity)
            )


        # ====================================================
        # NO HAND
        # ====================================================

        else:

            direction = "NONE"
            action = "NO ACTION"
            intensity = 0

            stable_direction = "NONE"
            candidate_direction = "NONE"

            direction_count = 0

            smooth_dx = 0.0
            smooth_dy = 0.0


        # ====================================================
        # DISPLAY ONLY THESE THREE
        # ====================================================

        cv2.putText(
            frame,
            f"Direction: {direction}",
            (20, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2
        )


        cv2.putText(
            frame,
            f"Action: {action}",
            (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2
        )


        cv2.putText(
            frame,
            f"Intensity: {intensity:.1f}%",
            (20, 135),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2
        )


        # ====================================================
        # SHOW WEBCAM
        # ====================================================

        cv2.imshow(
            "Dynamic Hand Control",
            frame
        )


        # ====================================================
        # EXIT
        # ====================================================

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break


# ============================================================
# CLEANUP
# ============================================================

cap.release()
cv2.destroyAllWindows()