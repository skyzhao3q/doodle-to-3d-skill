"""Export per-frame motion cues from a flight scene for the sound design (scripts/sfx.py).

Step 8a. blender -b WORK/out/<tag>.blend -P scripts/sfx_cues.py -- WORK  -> WORK/out/<tag>_cues.json
Per frame: near-wing flap angle (deg about Z), dragon root position, fire card scale (0 when hidden).
"""
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

sc = bpy.context.scene
dst = Work(sys.argv[sys.argv.index("--") + 1]).out / f"{sc['tag']}_cues.json"
# The first part with a wing role drives the flap sounds (none: no flaps).
wing_part = next((p for p, r in Work(sys.argv[sys.argv.index("--") + 1]).config()["rig"]["motion"].items()
                  if r == "wing"), None)
wing = bpy.data.objects.get(f"Pivot.{wing_part}") if wing_part else None
root = bpy.data.objects["Character"]
cards = [o for o in bpy.data.objects if o.name.startswith("FireCard.")]
cues = {"fps": sc.render.fps, "frames": []}
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    fire = max((o.scale.x for o in cards if not o.hide_render), default=0.0)
    p = root.matrix_world.translation
    cues["frames"].append({"wing": math.degrees(wing.rotation_euler.z) if wing else 0.0, "x": p.x, "z": p.z, "fire": fire})
json.dump(cues, open(dst, "w"))
print("cues", dst, len(cues["frames"]))
