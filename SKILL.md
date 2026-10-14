---
name: doodle-to-3d
description: Turn a child's hand drawing (photo or scan) into an animated 3D character that keeps the child's pencil lines and marker texture — cut out the character, split it into parts, fill in what the drawing hides or leaves out, then render flying / fire-breathing scenes in a child-drawn sky with synthesised sound effects. Use when someone wants to 3D-ify, animate or "bring to life" a doodle, kid's drawing or hand-drawn character.
---

# doodle-to-3d

Pipeline: photo → Gemini clean-up → transparent cutout → **parts (config.json)** → puffy 3D layers in Blender →
flight / fire scenes → sound effects → video → frozen asset library.
Everything except three Gemini image calls runs locally (Python + OpenCV, Blender, ffmpeg).

Read `README.md` (setup) and `docs/CONFIG.md` (config reference) once. Worked example:
`examples/purple-dragon/config.json`.

## Ground rules

- **Consent and privacy.** The drawing is sent to Google's Gemini API. Make sure the user (or the child's parent) is
  fine with that. Never commit drawings, renders or work directories to any repository.
- **Work directory outside this repo**, one per drawing: `WORK/input/<photo>`, `WORK/config.json`. All scripts take
  `WORK` as their first argument.
- **Keep the child's drawing.** Visible areas always use the original pixels; only hidden or missing areas are filled,
  and only with the child's own strokes (copied marker texture, mirrored parts) plus pencil outlines.
- **Never overwrite deliverables.** Each scene mode writes its own files; `make_video.py` refuses to overwrite;
  `freeze.py` makes read-only snapshots. New variants get new names.
- **Ask, don't guess, about what a shape is.** Children's drawings are ambiguous (a green square on the head may be
  the far wing, not an ear). Show the grid and ask the user before you build the parts.
- Gemini cost: about 3 image generations (~USD 0.1-0.2 each at the time of writing). Tell the user before calling it.

## Steps

1. **Check setup**: `python3 -c "import cv2, numpy, scipy, PIL, google.genai"`, `blender --version`,
   `ffmpeg -version`, and that `GEMINI_API_KEY` is set (never print it).
2. **Prepare**: put the photo in `WORK/input/`, then
   `python3 scripts/prepare.py WORK [--card]` (`--card` flattens a card / sheet photographed on a table).
   Look at `ref/source.png`: it must be upright.
3. **Write the first config fields**: `subject` (one sentence: colours, wings, tail…) and `extract_notes` (what to
   remove: text, frames, stars…).
4. **Clean-up (Gemini)**: `python3 scripts/gem.py extract WORK` → look at `ref/clean.png`. It must keep the child's
   lines; retry once if it "beautified" the drawing.
5. **Cutout**: `python3 scripts/cutout.py WORK`. All coordinates from now on are pixels of `ref/cutout.png`.
6. **Identify the parts**: `python3 scripts/grid.py WORK` (whole image), then crops at joints:
   `python3 scripts/grid.py WORK --crop X0 Y0 X1 Y1 --step 50 --scale 2`. Read the images. Make a list:
   - drawn parts → `cut` (wings, head, arms, legs, tail)
   - the body that continues behind them → `fill` (refill under the limbs, redraw its outline)
   - parts the child did not draw but the character needs (far wing, hidden arm) → `mirror` of the drawn twin
   - areas where a removed / rebuilt part overlapped another → `repaint` on that part
   **Confirm the list with the user** (which shape is what, what is missing) before writing polygons.
7. **Write `parts` in config.json** (compute order: a part may only refer to parts listed before it), run
   `python3 scripts/parts.py WORK`, and inspect `renders/parts_preview.png` and `renders/parts_sheet.png`.
   Iterate until every part is whole and nothing important is dropped. Tips:
   - outer edges of a `cut` polygon can be generous (the cutout alpha trims them); be precise only where parts meet
   - put the part that is drawn on top first and `minus` it from the parts behind
   - pivots go where the part attaches (shoulder, hip, wing root, neck, tail root)
   - pencil-only areas inside an outline (white paper) belong to the part; keep them
8. **Sky and clouds (Gemini)**: `python3 scripts/gem.py sky WORK && python3 scripts/clouds.py WORK`.
   Optional fire: `python3 scripts/gem.py fire WORK && python3 scripts/fire_frames.py WORK`, then set
   `fire.mouth` (the part that carries the mouth, and the mouth point; the flame leaves toward −x, i.e. screen-left).
9. **Rig and build**: fill `rig` (root part, draw order with depths, motions per part, `x_offset` to centre the
   character), then `blender -b -P scripts/flight.py -- WORK build swoop|hover|fire` and look at
   `renders/flight_<mode>_check/*.png`. Common fixes:
   | Symptom | Fix |
   |---|---|
   | part hidden behind another | adjust its `depth` (more negative = further in front) or the draw order |
   | character off-centre / cut at the frame edge | `rig.x_offset`, or `rig.swoop_path`, or `rig.camera_y` |
   | wings look narrow | lower `pose.wing_sweep` (mean angle back) |
   | flame not at the mouth / off screen | `fire.mouth.at`, `fire.length`, `fire.tilt`, `fire.yaw` |
   | seam shows when a limb moves | make the `fill` body cover the joint, or reduce that pose amplitude |
10. **Render**: `blender -b WORK/out/flight_<mode>.blend -P scripts/flight.py -- WORK render`
    (1080×1920, 24 fps; about 1 s per frame on a recent laptop — run it in the background).
11. **Sound**: `blender -b WORK/out/flight_<mode>.blend -P scripts/sfx_cues.py -- WORK` then
    `python3 scripts/sfx.py WORK flight_<mode> [--whoosh]` (`--whoosh` for swoop). Synthesised: wind, wing flaps on
    every downstroke, whooshes, inhale + fire roar. Say plainly that you cannot listen to it; check the timing with a
    spectrogram (`ffmpeg -i X.wav -lavfi showspectrumpic=s=1200x300 spec.png`) and ask the user to listen.
12. **Video**: `python3 scripts/make_video.py WORK flight_<mode>` → `out/flight_<mode>.mp4` and `_sfx.mp4`.
13. **Freeze** what the user wants to reuse: `python3 scripts/freeze.py WORK [name]` → `WORK/assets/<name>/`
    (read-only; scenes saved with images packed).

## Report to the user

Show the parts sheet and a few frames, say what was filled in or added (and why), what each Gemini call cost, what
you could not verify (sound), and where the files are.
