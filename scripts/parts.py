"""Step 5: split the drawing into character parts from config.json, keep its pencil lines, fill what it hides.

python3 scripts/parts.py WORK
Reads ref/cutout.png and config["parts"] (see docs/CONFIG.md). Writes:
  ref/parts/tex_<part>.png   texture per part (pencil lines darkened), canvas = cutout padded by config["pad"]
  out/parts.npz              grid masks + heights (px) + pivots, read by scripts/flight.py
  renders/parts_preview.png  part masks tinted over the drawing (check the split here)
  renders/parts_sheet.png    exploded view with labels
Part types:
  cut     a drawn part: alpha ∩ polygon, minus parts in front of it, plus extra regions
  fill    a body that continues behind other parts: the whole polygon; hidden areas are refilled with the
          child's own marker strokes (a tile copied from the least-lined patch) and its outline redrawn in pencil
  mirror  a part the child did not draw (far wing, hidden arm): an existing part mirrored, moved, turned, scaled
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work, color_ranges, find_font  # noqa: E402

GRAPHITE = (58, 52, 60)  # BGR

work = Work(sys.argv[1])
cfg = work.config()
PAD = int(cfg.get("pad", 260))
STEP = int(cfg.get("grid_step", 4))
PARTS = cfg["parts"]

src = cv2.imread(str(work.ref / "cutout.png"), cv2.IMREAD_UNCHANGED)
src = cv2.copyMakeBorder(src, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=(255, 255, 255, 0))
H, W = src.shape[:2]


def off(pts):
    return [(x + PAD, y + PAD) for x, y in pts]


def poly(pts):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.int32(off(pts))], 1)
    return m


def largest(m, close=0):
    m = m.astype(np.uint8)
    if close:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    return (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8) if n > 1 else m


alpha = (src[..., 3] > 127).astype(np.uint8)
alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
bgr = src[..., :3].copy()
bgr[alpha == 0] = 255
hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
RANGES = color_ranges(cfg)


def color_mask(name):
    r = RANGES[name]
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = (h >= r["h"][0]) & (h <= r["h"][1])
    if "h2" in r:
        m |= (h >= r["h2"][0]) & (h <= r["h2"][1])
    m &= s >= r.get("s_min", 0)
    if "v_max" in r:
        m &= v <= r["v_max"]
    return m.astype(np.uint8)


# ---------- pencil lines: grey strokes (and any very dark stroke) pushed toward graphite ----------
lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
diff = cv2.medianBlur(lab[..., 0], 31).astype(np.float32) - lab[..., 0].astype(np.float32)
line = np.clip((diff - 10) / 35, 0, 1) * np.clip((95 - hsv[..., 1].astype(np.float32)) / 50, 0, 1)
line = np.maximum(line, np.clip((diff - 45) / 30, 0, 1))
line = cv2.GaussianBlur(cv2.dilate(line, np.ones((3, 3), np.uint8)), (3, 3), 0)
k = (cfg.get("pencil_boost", 0.8) * line)[..., None]
tex = (bgr.astype(np.float32) * (1 - k) + np.float32(GRAPHITE) * k).astype(np.uint8)

# ---------- the child's marker, as a fill for hidden areas ----------
fill_cfg = cfg.get("fill", {})
fill_color = color_mask(fill_cfg.get("color", "purple"))
P = int(fill_cfg.get("patch", 110))
sx0, sy0, sx1, sy1 = fill_cfg.get("search", [0, 0, W - 2 * PAD, H - 2 * PAD])
best = None
for y in range(sy0 + PAD, sy1 + PAD - P, 20):
    for x in range(sx0 + PAD, sx1 + PAD - P, 20):
        win = (slice(y, y + P), slice(x, x + P))
        if fill_color[win].mean() > 0.97 and (best is None or line[win].mean() < best[0]):
            best = (line[win].mean(), x, y)
if best is None:
    raise SystemExit(f"no {P}px patch of solid fill colour found in fill.search; widen it or lower fill.patch")
_, px0, py0 = best
tile = np.tile(tex[py0:py0 + P, px0:px0 + P], (H // P + 2, W // P + 2, 1))
for ty in range(0, tile.shape[0], P):  # mirror alternate tiles so the copy does not read as a grid
    for tx in range(0, tile.shape[1], P):
        if (ty // P + tx // P) % 2:
            tile[ty:ty + P, tx:tx + P] = tile[ty:ty + P, tx:tx + P][:, ::-1]
tile = tile[:H, :W]

masks, textures = {}, {}


def cond(c, self_mask=None):
    if isinstance(c, dict) and "poly" in c:
        return poly(c["poly"])
    if c == "alpha":
        return alpha.copy()
    if c == "outside":
        return 1 - alpha
    if c == "self":
        return self_mask.copy()
    kind, _, name = c.partition(":")
    if kind == "color":
        return color_mask(name)
    if kind == "not_color":
        return 1 - color_mask(name)
    if kind in ("part", "under"):
        return masks[name].copy()
    raise SystemExit(f"unknown condition {c!r}")


def region(r, self_mask=None):
    """A region: a single condition, or {"all": [conditions], "dilate": px, "clip": [conditions]}."""
    if not (isinstance(r, dict) and "all" in r):
        return cond(r, self_mask)
    m = np.ones((H, W), np.uint8)
    for c in r["all"]:
        m &= cond(c, self_mask)
    if r.get("dilate"):
        m = cv2.dilate(m, np.ones((r["dilate"], r["dilate"]), np.uint8))
    for c in r.get("clip", []):
        m &= cond(c, self_mask)
    return m


def refill(base, where, edges=(), width=7):
    soft = cv2.GaussianBlur(where.astype(np.float32), (0, 0), 3)[..., None]
    out = (base * (1 - soft) + tile * soft).astype(np.uint8)
    pen = np.zeros((H, W), np.uint8)
    for e in edges:
        cv2.polylines(pen, [np.int32(off(e))], False, 1, width, cv2.LINE_AA)
    pen &= cv2.dilate(where.astype(np.uint8), np.ones((15, 15), np.uint8))
    out[pen > 0] = GRAPHITE
    return out


def warp(img, M, interp=cv2.INTER_LINEAR):
    return cv2.warpAffine(img, M, (W, H), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def mirror_matrix(spec, src_mask):
    """Mirror about the source pivot's vertical, then either map the farthest source point onto `tip`
    (similarity) or move to `pivot`, rotate by `rotate` deg and scale by `scale` about it."""
    sp = np.array(off([spec["src_pivot"]])[0], float)
    dp = np.array(off([spec["pivot"]])[0], float)
    Mm = np.array([[-1, 0, 2 * sp[0]], [0, 1, 0], [0, 0, 1]], float)
    if "tip" in spec:
        ys, xs = np.nonzero(src_mask)
        i = ((xs - sp[0]) ** 2 + (ys - sp[1]) ** 2).argmax()
        a, b = sp, (Mm @ [xs[i], ys[i], 1])[:2]
        va, vb = b - a, np.array(off([spec["tip"]])[0], float) - dp
        s = np.linalg.norm(vb) / np.linalg.norm(va)
        t = np.arctan2(vb[1], vb[0]) - np.arctan2(va[1], va[0])
    else:
        s, t = spec.get("scale", 1.0), np.radians(spec.get("rotate", 0.0))
    R = s * np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    M = np.eye(3)
    M[:2, :2] = R
    M[:2, 2] = dp - R @ sp
    return (M @ Mm)[:2]


for name, spec in PARTS.items():  # dict order = compute order (parts may refer to earlier ones)
    kind = spec.get("type", "cut")
    if kind == "cut":
        m = alpha & poly(spec["poly"])
        for other in spec.get("minus", []):
            m &= 1 - masks[other]
        for p in spec.get("minus_poly", []):
            m &= 1 - poly(p)
        for r in spec.get("add", []):
            m |= region(r) & alpha
        m = largest(m, spec.get("close", 0)) if spec.get("largest", True) else m
        t = tex
    elif kind == "fill":
        m = poly(spec["poly"])
        cover = np.zeros((H, W), np.uint8)
        for r in spec.get("refill", []):
            cover |= region(r, m)
        t = refill(tex, cover & m, spec.get("outline", []))
    elif kind == "mirror":
        M = mirror_matrix(spec, masks[spec["source"]])
        m = (warp(masks[spec["source"]], M, cv2.INTER_NEAREST) > 0).astype(np.uint8)
        t = warp(textures[spec["source"]], M)
    else:
        raise SystemExit(f"{name}: unknown type {kind}")
    if spec.get("repaint"):
        cover = np.zeros((H, W), np.uint8)
        for r in spec["repaint"]:
            cover |= region(r, m)
        t = refill(t, cover & m, spec.get("repaint_outline", []))
    masks[name], textures[name] = m, t


# ---------- heights ----------
def height(name, spec):
    hs = spec.get("height", {"puff": 0.8})
    if "plate" in hs:  # thin wing-like plate
        d = cv2.distanceTransform(masks[name], cv2.DIST_L2, 5)
        h = np.minimum(np.sqrt(d * 40.0) * 0.5, float(hs["plate"]))
        return cv2.GaussianBlur(h.astype(np.float32), (0, 0), 3)
    m = masks[name].copy()
    for other in hs.get("union", []):  # inflate together so the joint is continuous
        m |= masks[other]
    d = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    h = np.sqrt(d * max(d.max(), 1.0)) * float(hs["puff"]) * float(hs.get("scale", 1.0))
    return cv2.GaussianBlur(h.astype(np.float32), (0, 0), 4)


heights = {n: height(n, s) for n, s in PARTS.items()}

# ---------- outputs ----------
pdir = work.ref / "parts"
pdir.mkdir(exist_ok=True)
for name, t in textures.items():
    cv2.imwrite(str(pdir / f"tex_{name}.png"), t)


def grid(a):
    return cv2.resize(a.astype(np.float32), (W // STEP + 1, H // STEP + 1), interpolation=cv2.INTER_AREA)


pivots = {n: [s["pivot"][0] + PAD, s["pivot"][1] + PAD] for n, s in PARTS.items() if "pivot" in s}
arrays = {"step": STEP, "W": W, "H": H, "pad": PAD, "pivots": json.dumps(pivots), "names": json.dumps(list(PARTS))}
for name in PARTS:
    arrays[f"m_{name}"] = grid(masks[name]) > 0.5
    arrays[f"h_{name}"] = grid(heights[name])
np.savez_compressed(work.out / "parts.npz", **arrays)

rng = np.random.default_rng(3)
prev = tex.copy()
for name in PARTS:
    col = rng.integers(40, 255, 3)
    m = masks[name] > 0
    prev[m] = (0.55 * prev[m] + 0.45 * col).astype(np.uint8)
cv2.imwrite(str(work.renders / "parts_preview.png"), cv2.resize(prev, (W // 2, H // 2)))

fp = find_font()
font = ImageFont.truetype(fp, 40) if fp else ImageFont.load_default()
tiles = []
for name, spec in PARTS.items():
    m, t = masks[name], textures[name]
    ys, xs = np.nonzero(m)
    c_ = np.full((H, W, 3), 255, np.uint8)
    c_[m > 0] = t[m > 0]
    crop = Image.fromarray(cv2.cvtColor(c_[ys.min():ys.max() + 1, xs.min():xs.max() + 1], cv2.COLOR_BGR2RGB))
    kk = 380 / max(crop.size)
    crop = crop.resize((max(1, int(crop.width * kk)), max(1, int(crop.height * kk))))
    tile_ = Image.new("RGB", (420, 470), "white")
    tile_.paste(crop, ((420 - crop.width) // 2, 70 + (400 - crop.height) // 2))
    label = spec.get("label", name) if fp else name
    ImageDraw.Draw(tile_).text((210, 35), label, font=font, fill=(90, 50, 120), anchor="mm")
    tiles.append(tile_)
cols = 5
sheet = Image.new("RGB", (420 * cols, 470 * ((len(tiles) + cols - 1) // cols)), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, (420 * (i % cols), 470 * (i // cols)))
sheet.save(work.renders / "parts_sheet.png")
print("parts px", {n: int(m.sum()) for n, m in masks.items()}, "fill patch", (px0 - PAD, py0 - PAD))
