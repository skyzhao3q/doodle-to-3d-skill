"""Gemini image steps (Nano Banana Pro). Needs GEMINI_API_KEY in the environment (or a .env file).

python3 scripts/gem.py extract WORK   ref/source.png  -> ref/clean.png   character only, white background, child's lines kept
python3 scripts/gem.py sky WORK       ref/cutout_white.png -> ref/sky.png  sky backdrop in the same child style (9:16)
python3 scripts/gem.py fire WORK      ref/cutout_white.png -> ref/fire_sheet.png  3 flipbook frames of a breath blast

Each call is one image generation (roughly USD 0.1-0.2 at the time of writing; check current pricing).
The drawing is sent to Google's API: get the artist's (or parent's) consent first.
Override the model with GEMINI_IMAGE_MODEL.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work, load_dotenv  # noqa: E402

load_dotenv()
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")


def client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set (export it, or put it in a .env file; see README)")
    from google import genai
    return genai.Client(api_key=key)


def generate(prompt, src: Path, out: Path, aspect):
    from google.genai import types
    c = client()
    part = types.Part.from_bytes(data=src.read_bytes(), mime_type="image/png")
    for i in range(4):
        try:
            r = c.models.generate_content(
                model=MODEL, contents=[part, prompt],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                                   image_config=types.ImageConfig(aspect_ratio=aspect, image_size="2K")))
            for p in r.candidates[0].content.parts:
                if p.inline_data and p.inline_data.data:
                    out.write_bytes(p.inline_data.data)
                    print(out)
                    return
            raise RuntimeError("no image in the response")
        except Exception as e:  # preview models throw transient 429/5xx
            if i == 3:
                raise
            print("retry", i + 1, str(e)[:160])
            time.sleep(6 * (i + 1))


def extract_prompt(cfg):
    subject = cfg.get("subject", "the character")
    notes = cfg.get("extract_notes", "")
    return (
        f"This is a photo of a drawing a young child made by hand with markers and pencil: {subject}. "
        "Extract ONLY that character and redraw it on a pure white (#FFFFFF) background, flat and evenly lit, as if "
        "scanned. Remove everything else: paper edges, the table, handwritten text and numbers, frames, decorations, "
        f"paper shadows and stains. {notes} "
        "Keep the child's drawing faithful: same pose, same proportions, same wobbly pencil outlines, same marker "
        "colours and marker texture. Complete faint pencil-only parts as clean thin pencil lines; do not invent new "
        "parts. Do not make it look professional. Centre the character with a small margin. No text.")


SKY = (
    "A tall background painting of an empty blue sky with a few fluffy white clouds, drawn in exactly the same style "
    "as the reference image: a young child's drawing with felt-tip markers and wobbly grey pencil outlines on white "
    "paper, visible marker strokes, uneven colouring. Light sky blue at the bottom getting deeper blue at the top, "
    "5-6 round puffy clouds of different sizes with pencil outlines, a small yellow sun with pencil rays in one top "
    "corner. No characters, no animals, no text, no ground. Fill the whole frame edge to edge.")


def fire_prompt(cfg):
    color = cfg.get("fire", {}).get("color", "blue")
    return (
        "Three drawings of the same fire-breath blast, stacked in three rows on plain white paper, drawn in exactly the "
        "same style as the reference image: a young child's felt-tip marker colouring with wobbly grey pencil outlines, "
        f"visible marker strokes. Each blast is a long horizontal cone of {color.upper()} fire with a lighter inside and a "
        "pale yellow-white core, licking flame tongues and a few loose flame bits. The NARROW end is on the RIGHT "
        "(where it leaves the mouth) and it billows wider toward the LEFT. The three rows differ a little in the flame "
        "tongues, like frames of a hand-drawn animation; same size and position in each row, clear white gaps between "
        "rows. No character, no text, no background colour.")


def main():
    cmd, work = sys.argv[1], Work(sys.argv[2])
    cfg = work.config()
    if cmd == "extract":
        generate(extract_prompt(cfg), work.ref / "source.png", work.ref / "clean.png", cfg.get("extract_aspect", "3:4"))
    elif cmd == "sky":
        generate(SKY, work.ref / "cutout_white.png", work.ref / "sky.png", "9:16")
    elif cmd == "fire":
        generate(fire_prompt(cfg), work.ref / "cutout_white.png", work.ref / "fire_sheet.png", "9:16")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
