"""Cut the drawn clouds out of ref/sky.png as sprites (white fill + pencil outline) with inflation heights.

Step 6b. python3 scripts/clouds.py WORK -> WORK/ref/clouds/cloud_N.png, WORK/out/clouds.npz
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

WORK = Work(sys.argv[1])
STEP = 4
img = cv2.imread(str(WORK.ref / "sky.png"))
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
white = ((hsv[..., 1] < 45) & (hsv[..., 2] > 200)).astype(np.uint8)
white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
n, lab, stats, _ = cv2.connectedComponentsWithStats(white)
out = WORK.ref / "clouds"
out.mkdir(exist_ok=True)
data = {}
k = 0
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if area < 15000 or w > img.shape[1] * 0.8:
        continue
    m = (lab == i).astype(np.uint8)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    m = np.zeros_like(m)
    cv2.drawContours(m, cnts, -1, 1, thickness=cv2.FILLED)
    m = cv2.dilate(m, np.ones((11, 11), np.uint8))  # take the pencil outline with the fill
    pad = 12
    y0, y1, x0, x1 = max(y - pad, 0), y + h + pad, max(x - pad, 0), x + w + pad
    crop, cm = img[y0:y1, x0:x1].copy(), m[y0:y1, x0:x1]
    # Keep only the pencil line and white paper; the blue marker that bled into the dilated rim reads as dirt.
    chsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    blue = (chsv[..., 1] > 60) & (cm > 0)
    crop[blue] = (255, 255, 255)
    rim = cm & ~cv2.erode(cm, np.ones((5, 5), np.uint8))
    crop[(rim > 0) & blue] = (70, 64, 72)
    cv2.imwrite(str(out / f"cloud_{k}.png"), np.dstack([crop, cm * 255]))
    d = cv2.distanceTransform(cm, cv2.DIST_L2, 5)
    hh = cv2.GaussianBlur(np.sqrt(d * d.max()) * 0.7, (0, 0), 4)
    gw, gh = cm.shape[1] // STEP + 1, cm.shape[0] // STEP + 1
    data[f"mask{k}"] = cv2.resize(cm.astype(np.float32), (gw, gh), interpolation=cv2.INTER_AREA) > 0.5
    data[f"h{k}"] = cv2.resize(hh, (gw, gh), interpolation=cv2.INTER_AREA)
    data[f"size{k}"] = np.array([cm.shape[1], cm.shape[0]])
    k += 1
np.savez_compressed(WORK.out / "clouds.npz", n=k, step=STEP, **data)
print("clouds", k)
