"""Cut ref/fire_sheet.png (3 stacked flame drawings) into flipbook frames with alpha, aligned on the nozzle
(the narrow right end, where the flame leaves the mouth).

Step 6d. python3 scripts/fire_frames.py WORK -> WORK/ref/fire/fire_N.png (same size; nozzle at the middle of the right edge)
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

WORK = Work(sys.argv[1])
img = cv2.imread(str(WORK.ref / "fire_sheet.png"))
H, W = img.shape[:2]
ink = (img.min(2) < 215).astype(np.uint8)
ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
rows = np.nonzero(ink.sum(1) > 3)[0]
# Bands of inked rows separated by white gaps.
bands, start = [], rows[0]
for a, b in zip(rows, rows[1:]):
    if b - a > 25:
        bands.append((start, a))
        start = b
bands.append((start, rows[-1]))
bands = [b for b in bands if b[1] - b[0] > 150][:3]
assert len(bands) == 3, bands

frames = []
for y0, y1 in bands:
    band = img[y0:y1 + 1]
    m = (band.min(2) < 230).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    # Fill enclosed paper (pale core) so the flame is solid; drop specks.
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solid = np.zeros_like(m)
    bh, bw = m.shape
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        touches_edge = x <= 1 or y <= 1 or x + w >= bw - 1 or y + h >= bh - 1  # paper shading at the sheet edge
        if cv2.contourArea(c) > 300 and not touches_edge:
            cv2.drawContours(solid, [c], -1, 1, cv2.FILLED)
    ys, xs = np.nonzero(solid)
    # Nozzle = rightmost inked column of the main blob; its vertical centre there.
    main = max(cnts, key=cv2.contourArea)
    mx = main[:, 0, 0].max()
    tip_ys = main[main[:, 0, 0] >= mx - 6][:, 0, 1]
    frames.append((band, solid, (int(mx), int(tip_ys.mean())), (xs.min(), ys.min(), xs.max(), ys.max())))

# Common canvas: nozzle at (CW - 8, CH / 2).
left = max(f[2][0] - f[3][0] for f in frames)
up = max(f[2][1] - f[3][1] for f in frames)
down = max(f[3][3] - f[2][1] for f in frames)
CW, CH = left + 16, 2 * max(up, down) + 16
out = WORK.ref / "fire"
out.mkdir(exist_ok=True)
for i, (band, solid, (nx, ny), _) in enumerate(frames):
    M = np.float32([[1, 0, CW - 8 - nx], [0, 1, CH // 2 - ny]])
    rgb = cv2.warpAffine(band, M, (CW, CH), borderValue=(255, 255, 255))
    a = cv2.warpAffine(solid * 255, M, (CW, CH), borderValue=0)
    a = cv2.GaussianBlur(a, (3, 3), 0)
    cv2.imwrite(str(out / f"fire_{i}.png"), np.dstack([rgb, a]))
print("fire frames", (CW, CH), [f[2] for f in frames])
