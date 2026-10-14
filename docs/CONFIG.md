# config.json reference

One `config.json` per work directory. Coordinates are **pixels of `ref/cutout.png`** (read them off
`scripts/grid.py`). Points may be negative or beyond the image (the canvas is padded by `pad`), e.g. for a rebuilt
wing that reaches past the drawing. See `examples/purple-dragon/config.json`.

## Top level

| Key | Type | Meaning |
|---|---|---|
| `subject` | string | One sentence describing the character (used in the Gemini clean-up prompt) |
| `extract_notes` | string | What else to remove (handwriting, frames, stickers…) |
| `extract_aspect` | string | Aspect ratio for the clean-up image, default `"3:4"` |
| `pad` | int | Canvas padding around the cutout, default 260 |
| `pencil_boost` | float | How strongly grey pencil strokes are darkened, default 0.8 |
| `fill` | object | Marker texture used to fill hidden areas: `color` (named colour), `search` `[x0, y0, x1, y1]` where to look for a solid patch, `patch` size px (default 110) |
| `colors` | object | Extra / overriding colour ranges: `{"name": {"h": [min, max], "s_min": n, "h2": [..], "v_max": n}}` (OpenCV HSV, H 0-180). Built-in: green, purple, blue, red, orange, yellow, pink, brown |
| `parts` | object | Parts in **compute order** (see below) |
| `rig` | object | 3D layout and motion (see below) |
| `fire` | object | Fire-breath settings (optional) |

## parts

Each entry `"name": { ... }`. Common keys: `type` (`cut` / `fill` / `mirror`), `label` (shown on the parts sheet),
`pivot` `[x, y]` (where it attaches and rotates; required for every part except the rig root), `height`.

| type | Keys | Result |
|---|---|---|
| `cut` | `poly`, `minus` [parts], `minus_poly` [polys], `add` [regions], `close` (px), `largest` (default true) | drawn pixels inside `poly`, minus the listed parts / polygons, plus `add` regions (∩ drawing); morphological close; largest blob |
| `fill` | `poly`, `refill` [regions], `outline` [polylines] | the whole polygon (including hidden areas); `refill` regions get the child's marker texture, `outline` polylines are redrawn in pencil inside them |
| `mirror` | `source`, `src_pivot`, `pivot`, and either `tip` `[x, y]` or `rotate` (deg) + `scale` | the source part (mask + texture) mirrored about its pivot's vertical, moved to `pivot`; with `tip`, scaled/turned so the source's farthest point lands on `tip` |

Optional on any part: `repaint` [regions] + `repaint_outline` [polylines] — paint over areas of this part's texture
(e.g. where a rebuilt part used to overlap it).

`height`: `{"puff": k}` rounded inflation (0.7–0.85 typical), optionally `"union": [parts]` to inflate together
with neighbours (continuous joints) and `"scale"`; or `{"plate": px}` for thin parts such as wings.

### Regions

A region is a single condition or `{"all": [conditions], "dilate": px, "clip": [conditions]}` (AND of conditions,
then dilate, then AND with `clip`). Conditions:

| Condition | Meaning |
|---|---|
| `{"poly": [[x, y], ...]}` | inside the polygon |
| `"alpha"` / `"outside"` | drawn / not drawn |
| `"color:NAME"` / `"not_color:NAME"` | pixel colour in / not in the named range |
| `"part:NAME"` | that (earlier) part's mask |
| `"self"` | the current part's mask (in `fill` / `repaint`) |

## rig

| Key | Meaning |
|---|---|
| `root` | part that is the body (moves with the whole character, no pivot needed) |
| `draw` | back-to-front list of `{"part", "depth", "depth_ref", "shade", "outline"}`. `depth`: mid-plane offset as a fraction of `depth_ref`'s half-thickness at the part's pivot (+ behind, − in front; default ref = root); `"front"` = just in front |
| `plates` | parts rendered as thin plates (lighter shade, thinner outline) |
| `motion` | `{"part": role}`; roles: `wing`, `wing_mirror`, `head`, `tail`, `leg`, `leg_opposite`, `arm_wave`, `arm_swing`, `still` |
| `x_offset` | horizontal shift (units) so the character's visual centre sits mid-frame |
| `height_units` | character height in scene units, default 2.4 |
| `pose` | overrides: `wing_sweep`, `wing_flap`, `wing_dip`, `flaps` (per 10 s), `leg_kick`, `leg_swing`, `leg_cycles`, `arm_wave`, `arm_wave_cycles`, `arm_swing`, `head_nod`, `head_tilt`, `body_yaw`, `body_roll` (degrees / cycles per 10 s) |
| `swoop_path` | `[[t, x, z], ...]` keys (t 0–1) for the swoop flight; default enters from below, weaves, exits the top |
| `camera_y` | `{"swoop": -6.2, "fire": -6.0, "hover": -5.2}` overrides (more negative = further away) |

Rotation conventions (for custom poses): about Y turns a part within the picture plane, about X toward/away from
the camera, about Z swings it toward the camera (wing flap).

## fire

| Key | Default | Meaning |
|---|---|---|
| `color` | `"blue"` | flame colour for the Gemini prompt |
| `mouth` | — | `{"part": "head", "at": [x, y]}` where the flame starts |
| `times` | `[2, 3, 7]` | inhale start, blast start, blast end (s) |
| `length` | 1.4 | flame length (units) |
| `tilt` / `yaw` | −14 / 30 | degrees; negative tilt drops the far end, yaw turns the blast toward the camera |
| `fullness` | 1.25 | flame card height relative to the drawing |
