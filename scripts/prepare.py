"""Step 1: load the photo of the drawing, fix its orientation, optionally flatten a card / paper sheet.

python3 scripts/prepare.py WORK [--card]
  WORK/input/<image>  ->  WORK/ref/upright.png, WORK/ref/source.png (what Gemini will see)
  --card   find the bright paper/card on a darker table and warp it to a flat rectangle
HEIC needs `pip install pillow-heif` (or, on macOS, it falls back to `sips`).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

EXTS = {".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp", ".tif", ".tiff"}


def open_image(p: Path) -> Image.Image:
    if p.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            if shutil.which("sips"):
                tmp = Path(tempfile.mkdtemp()) / "in.png"
                subprocess.run(["sips", "-s", "format", "png", str(p), "--out", str(tmp)], check=True,
                               capture_output=True)
                p = tmp
            else:
                raise SystemExit("HEIC input: pip install pillow-heif (or convert the photo to PNG/JPG)")
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def flatten_card(bgr):
    """Paper is near-grey and bright; a wooden or coloured table is warmer. Warp the biggest such region."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    paper = ((hsv[..., 1] < 30) & (hsv[..., 2] > 180)).astype(np.uint8) * 255
    paper = cv2.morphologyEx(paper, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
    cnts, _ = cv2.findContours(paper, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    card = cv2.convexHull(max(cnts, key=cv2.contourArea))
    quad = cv2.boxPoints(cv2.minAreaRect(card))
    c = quad.mean(0)
    quad = quad[np.argsort(np.arctan2(quad[:, 1] - c[1], quad[:, 0] - c[0]))]  # TL, TR, BR, BL for small tilts
    w = int(max(np.linalg.norm(quad[0] - quad[1]), np.linalg.norm(quad[3] - quad[2])))
    h = int(max(np.linalg.norm(quad[0] - quad[3]), np.linalg.norm(quad[1] - quad[2])))
    M = cv2.getPerspectiveTransform(np.float32(quad), np.float32([[0, 0], [w, 0], [w, h], [0, h]]))
    return cv2.warpPerspective(bgr, M, (w, h))


def main():
    work = Work(sys.argv[1])
    files = sorted(p for p in work.input.glob("*") if p.suffix.lower() in EXTS) if work.input.exists() else []
    if not files:
        raise SystemExit(f"put the drawing in {work.input}/")
    img = open_image(files[0])
    img.save(work.ref / "upright.png")
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if "--card" in sys.argv:
        bgr = flatten_card(bgr)
    cv2.imwrite(str(work.ref / "source.png"), bgr)
    print("source", work.ref / "source.png", bgr.shape[1], "x", bgr.shape[0],
          "(check it is upright; rotate input/ yourself if not)")


if __name__ == "__main__":
    main()
