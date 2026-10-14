"""Shared helpers: work-directory layout, config, colour ranges, fonts. No third-party imports, so Blender's
bundled Python can use it too.

A work directory (one per drawing, kept OUTSIDE this repository) looks like:
  WORK/input/<photo or scan>      the drawing (jpg / png / heic)
  WORK/config.json                subject, parts, rig (see docs/CONFIG.md)
  WORK/ref/                       derived images (upright, source, clean, cutout, parts/, sky, clouds/, fire/)
  WORK/out/                       data, .blend scenes, cues, audio, videos
  WORK/renders/                   grids, previews, frame sequences
  WORK/assets/                    frozen read-only copies (scripts/freeze.py)
"""
import json
import os
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent

# OpenCV HSV ranges (H 0-180). A config may add its own under "colors".
COLORS = {
    "green": {"h": [35, 100], "s_min": 60},
    "purple": {"h": [115, 160], "s_min": 40},
    "blue": {"h": [95, 130], "s_min": 60},
    "red": {"h": [165, 180], "s_min": 70, "h2": [0, 8]},
    "orange": {"h": [8, 20], "s_min": 80},
    "yellow": {"h": [20, 35], "s_min": 70},
    "pink": {"h": [150, 172], "s_min": 35},
    "brown": {"h": [5, 20], "s_min": 50, "v_max": 160},
}

FONT_CANDIDATES = [
    os.environ.get("DOODLE3D_FONT", ""),
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]


class Work:
    def __init__(self, path):
        self.root = Path(path).expanduser().resolve()
        if not self.root.is_dir():
            raise SystemExit(f"work directory not found: {self.root}")
        self.input = self.root / "input"
        self.ref = self.root / "ref"
        self.out = self.root / "out"
        self.renders = self.root / "renders"
        for d in (self.ref, self.out, self.renders):
            d.mkdir(exist_ok=True)

    @property
    def config_path(self):
        return self.root / "config.json"

    def config(self):
        if not self.config_path.exists():
            return {}
        return json.loads(self.config_path.read_text(encoding="utf-8"))


def color_ranges(cfg):
    out = dict(COLORS)
    out.update(cfg.get("colors", {}))
    return out


def find_font():
    for p in FONT_CANDIDATES:
        if p and Path(p).exists():
            return p
    return None


def load_dotenv():
    """Read KEY=VALUE lines from ./.env or the repo's .env into os.environ (never overrides existing vars)."""
    for p in (Path.cwd() / ".env", SKILL / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
