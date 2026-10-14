"""Coordinate grid over the cutout, for reading part polygons / pivots off the drawing.

python3 scripts/grid.py WORK [--crop X0 Y0 X1 Y1] [--step 50] [--scale 1.0]
  -> renders/grid[_X0_Y0_X1_Y1].png ; labels are cutout pixels (the numbers to put in config.json)
Start with the whole image (step 100), then crop into each joint / overlap with step 50 and scale 2.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

args = sys.argv[1:]
work = Work(args[0])


def opt(name, n=1, default=None):
    if name in args:
        i = args.index(name)
        vals = [float(v) for v in args[i + 1:i + 1 + n]]
        return vals if n > 1 else vals[0]
    return default


im = Image.open(work.ref / "cutout_white.png").convert("RGB")
x0, y0, x1, y1 = [int(v) for v in opt("--crop", 4, [0, 0, im.width, im.height])]
step = int(opt("--step", 1, 100))
k = opt("--scale", 1, 1.0)
im = im.crop((x0, y0, x1, y1))
im = im.resize((int(im.width * k), int(im.height * k)))
d = ImageDraw.Draw(im)
for x in range((x0 // step) * step, x1 + 1, step):
    X = (x - x0) * k
    major = x % (step * 2) == 0
    d.line([(X, 0), (X, im.height)], fill=(255, 0, 0) if major else (255, 180, 180), width=1)
    if major:
        d.text((X + 2, 2), str(x), fill=(220, 0, 0))
for y in range((y0 // step) * step, y1 + 1, step):
    Y = (y - y0) * k
    major = y % (step * 2) == 0
    d.line([(0, Y), (im.width, Y)], fill=(255, 0, 0) if major else (255, 180, 180), width=1)
    if major:
        d.text((2, Y + 2), str(y), fill=(220, 0, 0))
name = "grid.png" if "--crop" not in args else f"grid_{x0}_{y0}_{x1}_{y1}.png"
im.save(work.renders / name)
print(work.renders / name)
