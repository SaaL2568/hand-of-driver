import cv2
import time
from pathlib import Path
from ultralytics import YOLO

MODEL_PATH = Path("models/gesture_yolo11n_best.pt")
CONF_THRESHOLD = 0.5

GESTURE_COMMAND_MAP = {
    "fist": "START / GO",
    "palm": "STOP",
    "like": "ACCELERATE",
    "dislike": "BRAKE",
    "peace": "LEFT TURN",
    "ok": "RIGHT TURN",
    "call": "HORN",
    "stop": "PANIC / EMERGENCY STOP",
    "no_gesture": "SAFE IDLE"
}

def drawOverlay(frame, gestureName, command, conf, fps):
    h, w, _ = frame.shape
    
    cv2.rectangle(frame, (0, 0), (w, 80), (30, 30, 30), -1)
    
    cv2.putText(frame, f"FPS: {fps:.1f}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    
    cv2.putText(frame, f"GESTURE: {gestureName.upper()} ({conf:.2f})", (150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cmdColor = (0, 255, 0)
    if gestureName == "stop":
        cmdColor = (0, 0, 255)
    elif gestureName in ["dislike", "palm"]:
        cmdColor = (0, 165, 255)
    elif gestureName == "no_gesture":
        cmdColor = (180, 180, 180)

    cv2.putText(frame, f"ACTION: {command}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cmdColor, 2)

def startLiveGestureControl():
    if not MODEL_PATH.exists():
        print(f"Error: Trained model not found at {MODEL_PATH}")
        return

    print(f"Loading trained gesture model from {MODEL_PATH}...")
    model = YOLO(MODEL_PATH)
    
    print("Opening webcam feed...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not access webcam device 0.")
        return

    print("Live Gesture Vehicle Control Active.")
    print("Press 'q' or 'ESC' to exit camera window.\n")

    prevTime = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame from webcam.")
            break

        currentTime = time.time()
        fps = 1.0 / (currentTime - prevTime) if (currentTime - prevTime) > 0 else 30.0
        prevTime = currentTime

        results = model.predict(frame, conf=CONF_THRESHOLD, verbose=False)
        
        activeGesture = "no_gesture"
        activeCommand = GESTURE_COMMAND_MAP["no_gesture"]
        highestConf = 0.0

        if len(results) > 0 and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            for box in boxes:
                classId = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                gName = model.names[classId].lower()
                
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                
                cmd = GESTURE_COMMAND_MAP.get(gName, "SAFE IDLE")
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{gName.upper()} {conf:.2f}", (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                if conf > highestConf:
                    highestConf = conf
                    activeGesture = gName
                    activeCommand = cmd

        drawOverlay(frame, activeGesture, activeCommand, highestConf, fps)
        
        cv2.imshow("Hand Gesture Vehicle Control System - Live Inference", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            print("Exiting live gesture control window.")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    startLiveGestureControl()
