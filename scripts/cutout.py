"""Step 3: white background -> transparent PNG. White is flood-filled from the image border only, so white areas
enclosed by the child's pencil lines (eye whites, uncoloured wings) stay part of the character.

python3 scripts/cutout.py WORK   ref/clean.png -> ref/cutout.png (RGBA, cropped) + ref/cutout_white.png
All part coordinates in config.json are pixels of ref/cutout.png.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

work = Work(sys.argv[1])
img = cv2.imread(str(work.ref / "clean.png"))
h, w = img.shape[:2]
near_white = (img.min(2) > 225).astype(np.uint8)
walls = cv2.dilate(1 - near_white, np.ones((5, 5), np.uint8))  # close tiny gaps in the pencil outline
fill = (1 - walls).astype(np.uint8)
mask = np.zeros((h + 2, w + 2), np.uint8)
for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
    if fill[y, x]:
        cv2.floodFill(fill, mask, (x, y), 2)
bg = cv2.dilate((fill == 2).astype(np.uint8), np.ones((5, 5), np.uint8))
alpha = cv2.GaussianBlur(((1 - bg) * 255).astype(np.uint8), (3, 3), 0)
n, lab, stats, _ = cv2.connectedComponentsWithStats((alpha > 127).astype(np.uint8))
alpha[lab != 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])] = 0  # keep the character, drop specks
ys, xs = np.nonzero(alpha)
pad = 24
y0, y1, x0, x1 = max(ys.min() - pad, 0), min(ys.max() + pad, h), max(xs.min() - pad, 0), min(xs.max() + pad, w)
out = np.dstack([img, alpha])[y0:y1, x0:x1]
cv2.imwrite(str(work.ref / "cutout.png"), out)
white = out[..., :3].copy()
white[out[..., 3] < 128] = 255
cv2.imwrite(str(work.ref / "cutout_white.png"), white)
print("cutout", out.shape[1], "x", out.shape[0], "px  (config coordinates are in this image)")
