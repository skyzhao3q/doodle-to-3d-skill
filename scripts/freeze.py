"""Step 10 (optional): freeze a reusable, read-only asset library so later runs can never overwrite it.

python3 scripts/freeze.py WORK [NAME]   -> WORK/assets/NAME/ (default: today's date)
Copies the cutout, parts textures + parts.npz, sky / clouds, fire frames, videos, sound and cues, and saves each
out/flight_*.blend with its images packed inside (needs `blender` on PATH). Then removes write permission.
"""
import datetime
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

work = Work(sys.argv[1])
name = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
dst = work.root / "assets" / name
if dst.exists():
    raise SystemExit(f"{dst} exists; pick another name (frozen assets are never overwritten)")
groups = {
    "drawing": [work.ref / n for n in ("source.png", "clean.png", "cutout.png", "cutout_white.png")],
    "parts": list((work.ref / "parts").glob("tex_*.png")) + [work.out / "parts.npz", work.renders / "parts_sheet.png"],
    "sky": [work.ref / "sky.png", work.out / "clouds.npz"] + list((work.ref / "clouds").glob("*.png")),
    "fire": [work.ref / "fire_sheet.png"] + list((work.ref / "fire").glob("*.png")),
    "videos": list(work.out.glob("flight_*.mp4")),
    "sfx": list(work.out.glob("flight_*_sfx.wav")) + list(work.out.glob("flight_*_cues.json")),
}
for group, files in groups.items():
    for f in files:
        if f.exists():
            (dst / group).mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst / group / f.name)
shutil.copy2(work.config_path, dst / "config.json")
pack = ("import bpy, sys; bpy.ops.file.pack_all(); "
        "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1], copy=True, compress=True)")
for blend in work.out.glob("flight_*.blend"):
    (dst / "scenes").mkdir(exist_ok=True)
    subprocess.run(["blender", "-b", str(blend), "--python-expr", pack, "--", str(dst / "scenes" / blend.name)],
                   check=True, capture_output=True)
for p in dst.rglob("*"):
    if p.is_file():
        p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
print("frozen", dst)
