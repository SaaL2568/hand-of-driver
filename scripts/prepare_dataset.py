"""
Dataset preparation script for hand gesture YOLO11 training.

Reads annotations.csv from HuggingFace (no XetHub / snapshot_download),
filters to the 9 target gesture classes, then downloads images in parallel
using a thread pool. Writes YOLO-format label .txt files alongside images.

Set HF_TOKEN in your environment for authenticated (faster) downloads:
    $env:HF_TOKEN = "hf_..."   (PowerShell)

Usage:
    .venv/Scripts/python.exe scripts/prepare_dataset.py
"""

import os
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"

import pandas as pd
from huggingface_hub import hf_hub_download
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ID = "ntsrigaud/hagrid-subset"
REPO_TYPE = "dataset"
HF_TOKEN = os.environ.get("HF_TOKEN")
DOWNLOAD_WORKERS = 16

TARGET_CLASSES = [
    "fist",
    "palm",
    "like",
    "dislike",
    "peace",
    "ok",
    "call",
    "stop",
    "no_gesture",
]

CLASS_NAME_TO_ID = {name: idx for idx, name in enumerate(TARGET_CLASSES)}

OUTPUT_DIR = Path("dataset")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def createDirectoryLayout(baseDir: Path) -> None:
    for split in ["train", "val", "test"]:
        (baseDir / "images" / split).mkdir(parents=True, exist_ok=True)
        (baseDir / "labels" / split).mkdir(parents=True, exist_ok=True)


def buildYoloLabel(classId: int, bbox, imgWidth: int, imgHeight: int) -> str:
    """Convert a bounding box to a normalised YOLO label line."""
    x, y, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    if x > 1.0 or y > 1.0 or w > 1.0 or h > 1.0:
        xCen = (x + w / 2.0) / imgWidth
        yCen = (y + h / 2.0) / imgHeight
        normW = w / imgWidth
        normH = h / imgHeight
    else:
        xCen = x + w / 2.0
        yCen = y + h / 2.0
        normW = w
        normH = h
    xCen  = min(max(xCen,  0.0),    1.0)
    yCen  = min(max(yCen,  0.0),    1.0)
    normW = min(max(normW, 0.0001), 1.0)
    normH = min(max(normH, 0.0001), 1.0)
    return f"{classId} {xCen:.6f} {yCen:.6f} {normW:.6f} {normH:.6f}\n"


def downloadOneSample(
    repoFilePath: str,
    classId: int,
    outSplit: str,
    destImg: Path,
    destLbl: Path,
    bboxRow: pd.Series,
) -> bool:
    """Download one image, save JPEG + YOLO label. Returns True on success."""
    try:
        localPath = hf_hub_download(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            filename=repoFilePath,
            token=HF_TOKEN,
        )
        img = Image.open(localPath).convert("RGB")
        img.save(destImg, format="JPEG", quality=92)
        imgWidth, imgHeight = img.size

        bboxCols = ["x", "y", "w", "h"]
        if all(c in bboxRow.index for c in bboxCols) and pd.notna(bboxRow.get("x")):
            label = buildYoloLabel(
                classId, [bboxRow["x"], bboxRow["y"], bboxRow["w"], bboxRow["h"]],
                imgWidth, imgHeight
            )
        else:
            label = f"{classId} 0.5 0.5 1.0 1.0\n"

        with open(destLbl, "w") as f:
            f.write(label)
        return True

    except Exception as e:
        print(f"  WARN [{repoFilePath}]: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def prepareDatasetMain() -> None:
    if HF_TOKEN:
        print("HF_TOKEN detected - using authenticated downloads.")
    else:
        print("No HF_TOKEN found - using unauthenticated (rate-limited) downloads.")
    print(f"Repo      : {REPO_ID}")
    print(f"Workers   : {DOWNLOAD_WORKERS}")
    print(f"Classes   : {TARGET_CLASSES}")
    print()

    createDirectoryLayout(OUTPUT_DIR)

    # Step 1: Fetch annotations.csv (tiny, fast)
    print("Fetching annotations.csv...")
    csvPath = hf_hub_download(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        filename="annotations.csv",
        token=HF_TOKEN,
    )
    df = pd.read_csv(csvPath)
    print(f"Total rows   : {len(df)}")
    print(f"Columns      : {list(df.columns)}")

    # Auto-detect column names
    gestureCol = next(
        (c for c in ["gesture", "label", "class", "category"] if c in df.columns), None
    )
    splitCol = next(
        (c for c in ["split", "subset", "partition", "set"] if c in df.columns), None
    )
    pathCol = next(
        (c for c in ["file_path", "path", "filename", "image_path", "image"] if c in df.columns), None
    )

    print(f"gesture col  : '{gestureCol}'")
    print(f"split col    : '{splitCol}'")
    print(f"file_path col: '{pathCol}'")
    if gestureCol:
        print(f"Unique gestures in CSV: {sorted(df[gestureCol].str.lower().unique())}")
    print()

    if gestureCol is None:
        print("ERROR: Cannot find a gesture/label column. Aborting.")
        return
    if pathCol is None:
        print("ERROR: Cannot find a file path column. Aborting.")
        return

    # Step 2: Filter to 9 target classes
    df["gesture_lower"] = df[gestureCol].str.lower()
    filtered = df[df["gesture_lower"].isin(TARGET_CLASSES)].copy().reset_index(drop=True)
    print(f"Kept {len(filtered)} samples (discarded {len(df)-len(filtered)} from other classes).")

    # Step 3: Normalise split labels
    SPLIT_REMAP = {"train": "train", "val": "val", "validation": "val", "test": "test"}
    if splitCol:
        filtered["out_split"] = (
            filtered[splitCol].str.lower().map(lambda s: SPLIT_REMAP.get(s, "train"))
        )
    else:
        print("No split column - assigning 70/15/15 per class.")
        parts = []
        for _, grp in filtered.groupby("gesture_lower"):
            n = len(grp)
            t = int(n * 0.70)
            v = t + int(n * 0.15)
            grp = grp.copy()
            grp["out_split"] = ["train"] * t + ["val"] * (v - t) + ["test"] * (n - v)
            parts.append(grp)
        filtered = pd.concat(parts).reset_index(drop=True)

    splitCounts = filtered["out_split"].value_counts()
    print(f"Split distribution: {dict(splitCounts)}")
    print()

    # Step 4: Build job list
    splitIndexes: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    jobs = []
    for _, row in filtered.iterrows():
        gestureName = row["gesture_lower"]
        classId     = CLASS_NAME_TO_ID[gestureName]
        outSplit    = row["out_split"]
        idx         = splitIndexes[outSplit]
        splitIndexes[outSplit] += 1

        repoFilePath = str(row[pathCol]).replace("\\", "/")
        stem         = f"img_{outSplit}_{classId}_{idx:07d}"
        destImg      = OUTPUT_DIR / "images" / outSplit / f"{stem}.jpg"
        destLbl      = OUTPUT_DIR / "labels" / outSplit / f"{stem}.txt"

        jobs.append((repoFilePath, classId, gestureName, outSplit, destImg, destLbl, row))

    # Step 5: Parallel download
    print(f"Downloading {len(jobs)} images with {DOWNLOAD_WORKERS} parallel workers...")
    totalSaved  = 0
    totalFailed = 0
    classCounters: dict[str, dict[str, int]] = {
        c: {"train": 0, "val": 0, "test": 0} for c in TARGET_CLASSES
    }

    def runJob(job):
        repoFilePath, classId, gestureName, outSplit, destImg, destLbl, row = job
        ok = downloadOneSample(repoFilePath, classId, outSplit, destImg, destLbl, row)
        return ok, gestureName, outSplit

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(runJob, job): job for job in jobs}
        done = 0
        for future in as_completed(futures):
            ok, gestureName, outSplit = future.result()
            done += 1
            if ok:
                totalSaved += 1
                classCounters[gestureName][outSplit] += 1
            else:
                totalFailed += 1
            if done % 200 == 0 or done == len(jobs):
                pct = done / len(jobs) * 100
                print(f"  [{done}/{len(jobs)}  {pct:.0f}%]  saved={totalSaved}  failed={totalFailed}")

    # Summary
    print()
    print("=" * 60)
    print("Dataset preparation complete.")
    print(f"Saved : {totalSaved}   Failed: {totalFailed}")
    print()
    print(f"{'Class':<15} {'Train':>8} {'Val':>8} {'Test':>8}")
    print("-" * 45)
    for c in TARGET_CLASSES:
        print(
            f"{c:<15} {classCounters[c]['train']:>8} "
            f"{classCounters[c]['val']:>8} {classCounters[c]['test']:>8}"
        )
    print("=" * 60)
    print("\nOutput: dataset/images/{train,val,test}/")
    print("        dataset/labels/{train,val,test}/")


if __name__ == "__main__":
    prepareDatasetMain()
