import os
import shutil
from pathlib import Path
from ultralytics import YOLO

PRETRAINED_MODEL = "yolo11n.pt"
DATASET_CONFIG = "gestures.yaml"
PROJECT_DIR = "runs"
RUN_NAME = "gestureModelV1"
NUM_EPOCHS = 41
IMAGE_SIZE = 640
INITIAL_BATCH_SIZE = 16
FALLBACK_BATCH_SIZE = 8
NUM_WORKERS = 2
BEST_MODEL_DESTINATION = Path("models/gesture_yolo11n_best.pt")

def trainGestureModel():
    print("Initializing YOLO11 gesture model training...")
    model = YOLO(PRETRAINED_MODEL)
    
    batchSize = INITIAL_BATCH_SIZE
    try:
        print(f"Starting training with batch size {batchSize}, imgsz {IMAGE_SIZE}, workers {NUM_WORKERS}, epochs {NUM_EPOCHS}...")
        results = model.train(
            data=DATASET_CONFIG,
            epochs=NUM_EPOCHS,
            imgsz=IMAGE_SIZE,
            batch=batchSize,
            workers=NUM_WORKERS,
            project=PROJECT_DIR,
            name=RUN_NAME,
            exist_ok=True
        )
    except RuntimeError as e:
        errorMsg = str(e).lower()
        if "out of memory" in errorMsg or "cuda" in errorMsg:
            print(f"CUDA out-of-memory detected with batch size {batchSize}. Falling back to batch size {FALLBACK_BATCH_SIZE}...")
            batchSize = FALLBACK_BATCH_SIZE
            model = YOLO(PRETRAINED_MODEL)
            results = model.train(
                data=DATASET_CONFIG,
                epochs=NUM_EPOCHS,
                imgsz=IMAGE_SIZE,
                batch=batchSize,
                workers=NUM_WORKERS,
                project=PROJECT_DIR,
                name=RUN_NAME,
                exist_ok=True
            )
        else:
            raise e

    print("\nRunning validation on validation split...")
    valResults = model.val(data=DATASET_CONFIG, split="val")
    
    print("\nPer-class Validation Metrics Report:")
    print(f"{'Class ID':<10} {'Class Name':<15} {'Precision':<12} {'Recall':<12} {'mAP50':<12} {'mAP50-95':<12}")
    print("-" * 75)
    
    classNames = valResults.names
    metrics = valResults.box
    
    for idx, classId in enumerate(metrics.ap_class_index):
        cName = classNames[classId]
        p = metrics.p[idx]
        r = metrics.r[idx]
        map50 = metrics.ap50[idx]
        map50_95 = metrics.ap[idx]
        print(f"{classId:<10} {cName:<15} {p:<12.4f} {r:<12.4f} {map50:<12.4f} {map50_95:<12.4f}")

    bestWeightPath = Path(PROJECT_DIR) / RUN_NAME / "weights" / "best.pt"
    if not bestWeightPath.exists():
        bestWeightPath = Path("runs/detect/runs") / RUN_NAME / "weights" / "best.pt"

    if bestWeightPath.exists():
        BEST_MODEL_DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bestWeightPath, BEST_MODEL_DESTINATION)
        print(f"\nSuccessfully saved best model checkpoint to {BEST_MODEL_DESTINATION}")
    else:
        print(f"\nWarning: Could not locate best weights at {bestWeightPath}")

if __name__ == "__main__":
    trainGestureModel()
