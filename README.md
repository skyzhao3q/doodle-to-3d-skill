# doodle-to-3d

Turn a child's hand drawing into an animated 3D character — **without losing the child's pencil lines** — and
make it fly through a child-drawn sky, breathe fire, with sound effects. Packaged as an agent skill so
**Claude Code, Codex and other coding agents** can reproduce the whole process.

> 子どもの落書き（写真）から、鉛筆線とマーカーの塗りを残したままキャラクターを切り出し、パーツ分割・描かれていない
> 部分の補完をして 3D 化し、空を飛ぶ／火を吐く動画（効果音付き）まで作るパイプラインです。Claude Code や Codex などの
> コーディングエージェントに読ませて同じ手順を再現できるよう、Skill 形式でまとめています。

## What it does

| Step | Tool | Output |
|---|---|---|
| Fix orientation, flatten a card / sheet | OpenCV | `ref/source.png` |
| Clean up: character only, white background, child's lines kept | Gemini (Nano Banana Pro) | `ref/clean.png` |
| Transparent cutout | OpenCV | `ref/cutout.png` |
| Split into parts; fill hidden areas with the child's own marker strokes; rebuild missing parts by mirroring | OpenCV + `config.json` | parts textures, parts sheet |
| Puffy 3D layers with pencil outlines, rig, flight / fire scenes | Blender (Eevee) | `.blend`, frame sequences |
| Child-style sky + clouds, fire-breath flipbook | Gemini | `ref/sky.png`, `ref/fire/` |
| Wind, wing flaps, whooshes, inhale + fire roar | NumPy / SciPy synthesis | `.wav` |
| Video with sound; read-only asset library | ffmpeg | `.mp4`, `assets/` |

Scenes: **swoop** (15 s, flies in, weaves, climbs out), **hover** (10 s), **fire** (11 s, inhales and breathes fire).
Output is 1080×1920 (vertical), 24 fps.

## Requirements

- Python 3.10+
- [Blender](https://www.blender.org/download/) on your `PATH` as `blender` — tested with **Blender 5.2** (Eevee);
  older 4.x versions are untested
- [ffmpeg](https://ffmpeg.org/) on your `PATH`
- A **Gemini API key** (image generation): three image calls per drawing, roughly USD 0.1–0.2 each at the time of
  writing — check current pricing
- macOS, Linux or Windows (developed on macOS)

## Setup

```bash
git clone https://github.com/skyzhao3q/doodle-to-3d-skill.git
cd doodle-to-3d-skill
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional, for iPhone photos (HEIC):
pip install pillow-heif
```

### Gemini API key

1. Create a key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Provide it as an environment variable (recommended):
   ```bash
   export GEMINI_API_KEY="your-key-here"
   ```
   or copy `.env.example` to `.env` (in the repo root or the directory you run from) and fill it in.
   `.env` is git-ignored — **never commit your key**, and don't paste it into chats or issues.
3. Optional: `GEMINI_IMAGE_MODEL` to use a different image model (default `gemini-3-pro-image-preview`).

Check everything:

```bash
python3 -c "import cv2, numpy, scipy, PIL, google.genai; print('python ok')"
blender --version
ffmpeg -version | head -1
python3 -c "import os; print('GEMINI_API_KEY set:', bool(os.environ.get('GEMINI_API_KEY')))"
```

## Use it with a coding agent

**Claude Code**: install as a personal skill, then ask e.g. *"Turn the drawing in ~/doodles/dragon.jpg into a flying
3D character"*.

```bash
git clone https://github.com/skyzhao3q/doodle-to-3d-skill.git ~/.claude/skills/doodle-to-3d
```

**Codex** (and other agents): run the agent inside the cloned repository — it reads `AGENTS.md`, which points to
`SKILL.md`. Codex versions with skill support can also load the folder as a skill (e.g. `~/.codex/skills/doodle-to-3d`).

The agent follows `SKILL.md`: it will show you coordinate grids and **ask you what each ambiguous shape is**
(children's drawings are hard to read — a green square might be a wing, not an ear) before it builds the parts.

## Run it by hand

```bash
WORK=~/doodles/dragon            # one work directory per drawing, OUTSIDE this repo
mkdir -p $WORK/input && cp photo.jpg $WORK/input/
cp examples/purple-dragon/config.json $WORK/config.json   # start from the example, then edit

python3 scripts/prepare.py $WORK --card          # --card: the drawing is a card/sheet on a table
python3 scripts/gem.py extract $WORK             # Gemini: clean-up (1 image)
python3 scripts/cutout.py $WORK
python3 scripts/grid.py $WORK                    # read coordinates; edit config.json "parts"
python3 scripts/parts.py $WORK                   # check renders/parts_preview.png, parts_sheet.png
python3 scripts/gem.py sky $WORK && python3 scripts/clouds.py $WORK                 # Gemini: sky (1 image)
python3 scripts/gem.py fire $WORK && python3 scripts/fire_frames.py $WORK           # Gemini: fire (1 image)

blender -b -P scripts/flight.py -- $WORK build fire                 # also: swoop, hover
blender -b $WORK/out/flight_fire.blend -P scripts/flight.py -- $WORK render
blender -b $WORK/out/flight_fire.blend -P scripts/sfx_cues.py -- $WORK
python3 scripts/sfx.py $WORK flight_fire                          # add --whoosh for swoop
python3 scripts/make_video.py $WORK flight_fire                   # -> out/flight_fire_sfx.mp4
python3 scripts/freeze.py $WORK v1                                # optional read-only snapshot
```

`config.json` is documented in [docs/CONFIG.md](docs/CONFIG.md). The example config describes a purple dragon drawn on
a trading card; its coordinates only fit that drawing, so treat it as a template.

## Privacy

- The drawing is uploaded to Google's Gemini API for the clean-up, sky and fire steps. Get the artist's (or parent's)
  consent first, and check your Gemini terms regarding data use.
- Keep work directories outside this repository. `.gitignore` excludes images, videos, audio, `.blend` files and
  `.env`, but don't rely on it alone.
- No drawings or renders are included in this repository.

## Limitations

- Part outlines are written by hand (by you or the agent) per drawing; there is no automatic segmentation.
- The 3D is "puffy layers" built from the drawing, so it looks best within about ±40° of the front view.
- Sound effects are synthesised and simple; listen before you share.
- Rendering takes about 1 s per frame (Eevee, 1080×1920) on a recent laptop.

## License

MIT — see [LICENSE](LICENSE).
