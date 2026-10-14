"""Step 7: flying scenes in Blender. The parts from parts.py become puffy 3D layers that keep the child's
pencil lines as texture; they flap / paddle / wave according to config["rig"], in a sky of puffed-up drawn clouds.

blender -b -P scripts/flight.py -- WORK build [swoop|hover|fire]   -> WORK/out/<tag>.blend + renders/<tag>_check/
blender -b WORK/out/<tag>.blend -P scripts/flight.py -- WORK render -> WORK/renders/<tag>/NNNN.png (1080x1920, 24 fps)
  tag = flight_swoop (15 s: flies in, weaves, climbs out) / flight_hover (10 s: rises in place) /
        flight_fire (11 s: hovers, inhales, breathes fire from config["fire"]["mouth"])
Needs ref/parts (parts.py), ref/sky.png + out/clouds.npz (gem.py sky, clouds.py), and for fire ref/fire/ (gem.py fire,
fire_frames.py).
"""
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:]
WORK = Work(ARGS[0])
CFG = WORK.config()
RIG = CFG["rig"]
KEY = Vector((-0.5, -0.6, 0.62)).normalized()
MODE = ARGS[2] if len(ARGS) > 2 else "swoop"
FRAMES = {"hover": 240, "swoop": 360, "fire": 264}[MODE]
TAG = f"flight_{MODE}"  # each mode writes its own files
FIRE = {"times": [2.0, 3.0, 7.0], "length": 1.4, "tilt": -14, "yaw": 30, "fullness": 1.25, **CFG.get("fire", {})}
FIRE_T = tuple(FIRE["times"])  # inhale start, blast start, blast end (s)
X0 = float(RIG.get("x_offset", 0.0))  # shifts the character so its visual centre sits mid-frame
# Swoop path (time 0-1, x, z) in the character plane: enters from below, weaves, climbs out the top.
SWOOP = [tuple(p) for p in RIG.get("swoop_path", [
    (0.0, -0.8, -3.9), (0.06, -0.8, -3.9), (0.20, -0.22, 0.05), (0.36, 0.32, 0.35), (0.52, -0.28, -0.15),
    (0.68, 0.30, 0.25), (0.80, 0.02, 0.10), (0.93, 0.42, 4.3), (1.0, 0.42, 4.3)])]
DRAGON_H = float(RIG.get("height_units", 2.4))
CAM_Y = {"swoop": -6.2, "fire": -6.0, "hover": -5.2, **RIG.get("camera_y", {})}[MODE]
LENS = 50.0
HALF_FOV = math.atan(18 / LENS)  # vertical, portrait frame with sensor fit AUTO (36 mm along the long side)
GRAPHITE = (0.045, 0.04, 0.05, 1)
# Pose / motion tuning (degrees). Wing "sweep" is the mean angle about Z (+ = tips back, foreshortened);
# "flap" the stroke amplitude about Z; "dip" the in-plane tip drop on the downstroke.
POSE = {
    "wing_sweep": 4, "wing_flap": 40, "wing_dip": 10, "flaps": 12,
    "leg_kick": 18, "leg_swing": 7, "leg_cycles": 8,
    "arm_wave": 18, "arm_wave_cycles": 16, "arm_swing": 8,
    "head_nod": 2.5, "head_tilt": 3, "body_yaw": 14, "body_roll": 4,
    **RIG.get("pose", {}),
}


def link(o):
    bpy.context.collection.objects.link(o)
    return o


# ---------- materials ----------

def outline_material():
    m = bpy.data.materials.new("pencil_outline")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = GRAPHITE
    nt.links.new(em.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    m.use_backface_culling = True
    return m


def drawing_material(name, tex_path, shade=0.84):
    """Drawing texture as emission, times a soft two-step shade so the volume reads without hiding the strokes."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(tex_path))
    tex.image.alpha_mode = "NONE"
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = KEY
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (shade, shade * 0.97, shade * 1.03, 1)
    ramp.color_ramp.elements[1].position = 0.05
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], ramp.inputs[0])
    nt.links.new(tex.outputs["Color"], mul.inputs[6])
    nt.links.new(ramp.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


# ---------- inflated layer mesh ----------

def grid_mesh(name, mask, h, step, img_w, img_h, scale, mat, depth=1.0, y0=0.0, outline=0.012):
    """Closed puffy mesh from a grid mask + heights (px). Rim vertices (touching the outside) are shared by
    front and back at depth 0. UVs map back onto the full drawing (img_w x img_h px)."""
    rows, cols = mask.shape
    pad = np.pad(mask, 1)
    inside8 = np.ones_like(mask)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            inside8 &= pad[1 + dr:1 + dr + rows, 1 + dc:1 + dc + cols]
    rim = mask & ~inside8
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    front, back, uvs = {}, {}, {}
    for r, c in zip(*np.nonzero(mask)):
        x, z = (c * step - img_w / 2) * scale, (img_h / 2 - r * step) * scale
        d = 0.0 if rim[r, c] else float(h[r, c]) * scale * depth
        front[r, c] = bm.verts.new((x, y0 - d, z))
        back[r, c] = front[r, c] if rim[r, c] else bm.verts.new((x, y0 + d, z))
        uvs[r, c] = (min(c * step / img_w, 1.0), max(1 - r * step / img_h, 0.0))
    for r in range(rows - 1):
        for c in range(cols - 1):
            q = [(r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c)]
            if not all(mask[k] for k in q):
                continue
            for side, rev in ((front, False), (back, True)):
                ks = q[::-1] if rev else q
                vs = [side[k] for k in ks]
                if len(set(vs)) < 3:
                    continue
                try:
                    f = bm.faces.new(vs)
                except ValueError:  # all-rim quad, already made by the other side
                    continue
                for loop, k in zip(f.loops, ks):
                    loop[uv].uv = uvs[k]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(name, me))
    for p in me.polygons:
        p.use_smooth = True
    o.data.materials.append(mat)
    o.data.materials.append(OUTLINE)
    sol = o.modifiers.new("outline", "SOLIDIFY")
    sol.thickness, sol.offset, sol.use_flip_normals, sol.use_rim, sol.material_offset = outline, 1.0, True, False, 1
    return o


def empty(name, loc, parent=None):
    e = link(bpy.data.objects.new(name, None))
    e.location = loc
    e.rotation_mode = "XYZ"
    if parent:
        bpy.context.view_layer.update()
        e.parent = parent
        e.matrix_parent_inverse = parent.matrix_world.inverted()
    return e


def parent_keep(o, p):
    bpy.context.view_layer.update()
    o.parent = p
    o.matrix_parent_inverse = p.matrix_world.inverted()


# ---------- scene ----------

def build_dragon():
    """config["rig"]["draw"]: back-to-front list of {"part", "depth", "depth_ref", "shade", "outline"}.
    depth: where the part's mid-plane sits relative to the surface of depth_ref (default: the root part) at the
    part's pivot, as a fraction of that half-thickness (+ behind, - in front); "front" = just in front (head)."""
    g = np.load(WORK.out / "parts.npz")
    step, W, H, pad = int(g["step"]), int(g["W"]), int(g["H"]), int(g["pad"])
    pv = json.loads(str(g["pivots"]))
    S = DRAGON_H / (H - 2 * pad)
    root_part = RIG["root"]

    def P(px, py, y=0.0):  # padded drawing px -> 3D
        return Vector(((px - W / 2) * S, y, (H / 2 - py) * S))

    def h_at(part, px, py):
        return float(g[f"h_{part}"][int(py / step), int(px / step)]) * S

    root = empty("Character", (0, 0, 0))
    pivots = {}
    for d in RIG["draw"]:
        name, depth = d["part"], d.get("depth", 0.0)
        if depth == "front":
            y0 = -0.03  # just in front of whatever it overlaps
        elif depth == 0.0 or name == root_part:
            y0 = 0.0
        else:
            y0 = depth * h_at(d.get("depth_ref", root_part), *pv[name])
        plate = name in RIG.get("plates", [])
        mat = drawing_material(name, WORK.ref / f"parts/tex_{name}.png", d.get("shade", 0.9 if plate else 0.84))
        o = grid_mesh(f"Part.{name}", g[f"m_{name}"], g[f"h_{name}"], step, W, H, S, mat, y0=y0,
                      outline=d.get("outline", 0.008 if plate else 0.011))
        if name == root_part:
            parent_keep(o, root)
            continue
        e = empty(f"Pivot.{name}", P(*pv[name], y0), root)
        parent_keep(o, e)
        pivots[name] = e
    return root, pivots


def build_sky(cam):
    """Backdrop: the Gemini sky drawing on a far plane that slowly drifts down (we are rising)."""
    dist = 36.0
    view_h = 2 * dist * math.tan(HALF_FOV)
    img = bpy.data.images.load(str(WORK.ref / "sky.png"))
    ph = view_h * 1.3
    pw = ph * img.size[0] / img.size[1]
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, CAM_Y + dist, 0), rotation=(math.radians(90), 0, 0))
    plane = bpy.context.object
    plane.name = "Sky"
    plane.scale = (pw, ph, 1)
    m = bpy.data.materials.new("sky")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(t.outputs["Color"], em.inputs[0])
    nt.links.new(em.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    plane.data.materials.append(m)
    slack = (ph - view_h) / 2 * 0.9
    for f in (0, FRAMES):
        plane.location.z = slack - 2 * slack * f / FRAMES
        plane.keyframe_insert("location", frame=f)
    for fc in iter_fcurves(plane):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def build_clouds():
    """Puffy drawn clouds streaming downward at several depths; nearer ones pass faster (parallax)."""
    g = np.load(WORK.out / "clouds.npz")
    step = int(g["step"])
    rnd = random.Random(7)
    mats = [drawing_material(f"cloud{k}", WORK.ref / f"clouds/cloud_{k}.png", 0.9) for k in range(int(g["n"]))]
    # (depth from the dragon plane, x, width, phase): spread so the dragon is never covered for long.
    layout = [(-2.4, -2.1, 1.4, 0.10), (-2.0, 2.2, 1.6, 0.62), (1.5, -2.8, 2.2, 0.35), (2.0, 3.0, 2.6, 0.85),
              (6.0, -4.4, 3.6, 0.50), (7.5, 4.6, 3.4, 0.20), (10.0, -0.5, 3.6, 0.72)]
    for i, (dy, x, width, phase) in enumerate(layout):
        k = i % int(g["n"])
        mask, h, (sw, sh) = g[f"mask{k}"], g[f"h{k}"], g[f"size{k}"]
        S = width / float(sw)
        o = grid_mesh(f"Cloud.{i}", mask, h, step, float(sw), float(sh), S, mats[k], depth=0.8, outline=0.014)
        dist = dy - CAM_Y
        half = dist * math.tan(HALF_FOV)
        top, bottom = half + sh * S / 2 + 0.2, -half - sh * S / 2 - 0.2
        period = int(min(max(70 + 22 * dist, 80), FRAMES))  # frames to cross the view
        # Whole number of crossings per clip so the clip loops cleanly.
        period = FRAMES // max(1, round(FRAMES / period))
        o.rotation_euler = (0, rnd.uniform(-0.15, 0.15), 0)
        for f in range(FRAMES + 1):
            t = ((f / period) + phase) % 1.0
            o.location = (x + 0.15 * math.sin(2 * math.pi * (f / FRAMES + phase)), dy, top + (bottom - top) * t)
            o.keyframe_insert("location", frame=f)
        for fc in iter_fcurves(o):  # wrap jumps happen off screen; never interpolate across them
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def catmull(points, t):
    """Smooth path through (t, x, z) keys (Catmull-Rom, uniform within each segment)."""
    ts = [p[0] for p in points]
    i = max(0, min(len(points) - 2, next((k for k in range(len(ts) - 1) if ts[k + 1] >= t), len(ts) - 2)))
    p0, p1, p2, p3 = (Vector(points[max(0, min(len(points) - 1, j))][1:]) for j in (i - 1, i, i + 1, i + 2))
    u = 0.0 if ts[i + 1] == ts[i] else (t - ts[i]) / (ts[i + 1] - ts[i])
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def fire_env(sec):
    """(inhale, blast) weights in 0..1 for the fire mode."""
    t0, t1, t2 = FIRE_T
    inhale = smoothstep(t0, t1 - 0.2, sec) * (1 - smoothstep(t1 - 0.2, t1 + 0.1, sec))
    blast = smoothstep(t1 - 0.05, t1 + 0.2, sec) * (1 - smoothstep(t2 - 0.3, t2 + 0.2, sec))
    return inhale, blast


def key_dragon(root, pv):
    flap_phase = 0.0
    for f in range(FRAMES + 1):
        sec = f / 24
        w = 2 * math.pi * sec / 10  # base cycle (10 s), so motion speeds do not depend on the clip length
        if MODE == "swoop":
            t = f / FRAMES
            pos, ahead = catmull(SWOOP, t), catmull(SWOOP, min(t + 1 / FRAMES, 1.0))
            vx, vz = (ahead - pos) * 24  # units / s
            root.location = (X0 + pos.x + 0.04 * math.sin(10 * w), 0, pos.y + 0.06 * math.sin(10 * w))
            # Turn toward the direction of travel and bank into it; lean forward when climbing hard.
            yaw = max(-28.0, min(28.0, 22 * vx))
            bank = max(-14.0, min(14.0, 10 * vx))  # + about Y dips the +x side: lean into the turn
            pitch = max(-6.0, min(10.0, 2.5 * vz))
            root.rotation_euler = (math.radians(pitch + 2 * math.sin(4 * w)), math.radians(bank), math.radians(yaw))
            flap_rate = POSE["flaps"] / 10 * (1 + 0.35 * max(0.0, min(vz, 2.0)))  # flaps / s, faster on climbs
        elif MODE == "fire":
            inhale, blast = fire_env(sec)
            shake = 0.012 * blast * math.sin(sec * 47)
            # Hover; lean back and rise a little on the inhale, push forward and recoil during the blast.
            # Slides right for the blast so the flame (going left) has room in the frame.
            root.location = (X0 + 0.08 + 0.06 * math.sin(2 * w) + 0.42 * max(inhale, blast) + shake, 0,
                             0.08 * math.sin(10 * w) + 0.10 * inhale - 0.04 * blast)
            root.rotation_euler = (math.radians(2 * math.sin(4 * w) - 6 * inhale + 5 * blast),
                                   math.radians(-3 * inhale + 4 * blast),
                                   math.radians(8 * math.sin(w) - 10 * blast))
            flap_rate = POSE["flaps"] / 10 * (1 + 0.6 * blast)
        else:
            root.location = (X0 + 0.10 * math.sin(2 * w), 0, 0.10 * math.sin(10 * w))
            root.rotation_euler = (math.radians(3 * math.sin(4 * w)),
                                   math.radians(POSE["body_roll"] * math.sin(3 * w + 0.4)),
                                   math.radians(POSE["body_yaw"] * math.sin(w)))
            flap_rate = POSE["flaps"] / 10
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
        inhale, blast = fire_env(sec) if MODE == "fire" else (0.0, 0.0)
        # Flap: quick downstroke (toward the camera, tips dipping), slower recovery (back, tips up).
        ph = flap_phase % 1.0
        flap_phase += flap_rate / 24
        s = math.sin(math.pi * ph / 0.4) if ph < 0.4 else -math.sin(math.pi * (ph - 0.4) / 0.6)
        z = math.radians(POSE["wing_sweep"] - POSE["wing_flap"] * s * (1 - 0.5 * inhale if MODE == "fire" else 1))
        dip = math.radians(POSE["wing_dip"] * s)
        lp = POSE["leg_cycles"] * w
        aw = POSE["arm_wave_cycles"] * w
        # Rotation about Y turns a part in the picture plane, about X toward / away from the camera.
        poses = {
            "wing": (0, dip, z),
            "wing_mirror": (0, -dip, -z),  # the mirrored wing's tip points the other way: both angles flip
            "head": (math.radians(POSE["head_nod"] * math.sin(4 * w + 0.8) - 10 * inhale + 6 * blast),
                     math.radians(POSE["head_tilt"] * math.sin(2 * w) - 5 * inhale + 3 * blast
                                  + 1.5 * blast * math.sin(sec * 31)), 0),
            "tail": (math.radians(10 * math.sin(6 * w + 1.0)), math.radians(7 * math.sin(6 * w)), 0),
            "leg": (math.radians(POSE["leg_kick"] * math.sin(lp)), math.radians(POSE["leg_swing"] * math.sin(lp + 0.6)), 0),
            "leg_opposite": (math.radians(-POSE["leg_kick"] * math.sin(lp)),
                             math.radians(-POSE["leg_swing"] * math.sin(lp + 0.6)), 0),
            "arm_wave": (math.radians(4 * math.sin(aw + 0.5)), math.radians(POSE["arm_wave"] * math.sin(aw)), 0),
            "arm_swing": (math.radians(6 * math.sin(6 * w)), math.radians(-POSE["arm_swing"] * math.sin(6 * w + 1.2)), 0),
            "still": (0, 0, 0),
        }
        for part, role in RIG["motion"].items():
            pv[part].rotation_euler = poses[role]
        for e in pv.values():
            e.keyframe_insert("rotation_euler", frame=f)


def mouth_locator(pivots):
    """Empty riding on the mouth's part at the drawn mouth (config fire.mouth = {"part", "at": [x, y]}). Must be
    made in the rest pose (before key_dragon): the nozzle is computed in the drawing's own coordinates."""
    g = np.load(WORK.out / "parts.npz")
    step, W, H, pad = int(g["step"]), int(g["W"]), int(g["H"]), int(g["pad"])
    S = DRAGON_H / (H - 2 * pad)
    part = FIRE["mouth"]["part"]
    mx, my = FIRE["mouth"]["at"][0] + pad, FIRE["mouth"]["at"][1] + pad
    head_front = float(g[f"h_{part}"][int(my / step), int(mx / step)]) * S
    head_pivot = pivots[part]
    return empty("MouthLoc", Vector(((mx - W / 2) * S, -0.03 - head_front - 0.025, (H / 2 - my) * S)), head_pivot)


def build_fire(loc):
    """Fire breath: the three drawn flame frames as cards at the mouth, flipped like a hand-drawn animation
    (8 fps), growing out of the mouth at the start of the blast and shrinking at the end."""
    nozzle = loc.matrix_world.translation.copy()
    # The flame only follows the mouth's position, so the body's yaw never swings the flat drawing edge-on or
    # behind the wing. It stays facing the camera, turned a little toward it.
    sc = bpy.context.scene
    base = empty("Fire", nozzle)
    base.rotation_euler = (0, math.radians(FIRE["tilt"]), math.radians(FIRE["yaw"]))
    cards = []
    for i in range(3):
        img = bpy.data.images.load(str(WORK.ref / f"fire/fire_{i}.png"))
        fw, fh = img.size
        L, Hh = FIRE["length"], FIRE["length"] * fh / fw * FIRE["fullness"]
        me = bpy.data.meshes.new(f"FireCard.{i}")
        # Nozzle (middle of the right edge) at the origin, flame toward -x.
        me.from_pydata([(-L, 0, -Hh / 2), (0, 0, -Hh / 2), (0, 0, Hh / 2), (-L, 0, Hh / 2)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new()
        for loop, co in zip(me.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            uv.data[loop.index].uv = co
        o = link(bpy.data.objects.new(f"FireCard.{i}", me))
        m = bpy.data.materials.new(f"fire{i}")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        em = nt.nodes.new("ShaderNodeEmission")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Color"], em.inputs[0])
        nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        else:
            m.blend_method = "BLEND"
        o.data.materials.append(m)
        o.parent = base
        o.location = (0, -0.002 * i, 0)
        cards.append(o)
    t0, t1, t2 = FIRE_T
    for f in range(FRAMES + 1):
        sc.frame_set(f)
        base.location = loc.matrix_world.translation
        base.keyframe_insert("location", frame=f)
    for f in range(FRAMES + 1):
        sec = f / 24
        grow = smoothstep(t1 - 0.05, t1 + 0.3, sec) * (1 - smoothstep(t2 - 0.35, t2 + 0.1, sec))
        flick = 1 + 0.06 * math.sin(sec * 37) + 0.04 * math.sin(sec * 23 + 1)
        on = grow > 0.01
        frame_i = int(sec * 8) % 3
        for i, o in enumerate(cards):
            o.scale = (max(grow, 0.001) * flick, 1, (0.55 + 0.45 * grow) * (2 - flick))
            o.hide_render = not (on and i == frame_i)
            o.keyframe_insert("scale", frame=f)
            o.keyframe_insert("hide_render", frame=f)
    sc.frame_set(0)
    return base


def iter_fcurves(obj):
    act = obj.animation_data.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out


def setup(cam_target=(0, 0, 0.05)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.75, 0.95, 1)
    sc.world = w
    cam = link(bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")))
    cam.data.lens = LENS
    cam.data.clip_end = 200
    cam.location = (0, CAM_Y, 0.15)
    cam.rotation_euler = (Vector(cam_target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    return cam


def render(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    sc = bpy.context.scene
    if ARGS[1] == "build":
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob)
        OUTLINE = outline_material()
        cam = setup()
        root, pivots = build_dragon()
        mouth = mouth_locator(pivots) if MODE == "fire" else None
        key_dragon(root, pivots)
        if MODE == "fire":
            build_fire(mouth)
        sc["tag"] = TAG
        build_sky(cam)
        build_clouds()
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK.out / f"{TAG}.blend"))
        sc.render.resolution_percentage = 50
        checks = {"swoop": (40, 80, 130, 190, 250, 320), "fire": (30, 60, 75, 90, 130, 200)}
        for f in checks.get(MODE, (0, 3, 8, 60, 120, 180)):
            sc.frame_set(f)
            render(WORK.renders / f"{TAG}_check/{f:04d}.png")
    elif ARGS[1] == "render":
        sc.render.resolution_percentage = 100
        tag = sc["tag"]
        for f in range(sc.frame_end + 1):
            sc.frame_set(f)
            render(WORK.renders / f"{tag}/{f:04d}.png")
