"""Step 9: encode a rendered frame sequence and mux its sound effects. Never overwrites an existing video.

python3 scripts/make_video.py WORK TAG
  WORK/renders/TAG/%04d.png -> WORK/out/TAG.mp4 (silent)
  + WORK/out/TAG_sfx.wav    -> WORK/out/TAG_sfx.mp4 (with sound), if the wav exists
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Work  # noqa: E402

work, tag = Work(sys.argv[1]), sys.argv[2]
frames = work.renders / tag
silent, sound, wav = work.out / f"{tag}.mp4", work.out / f"{tag}_sfx.mp4", work.out / f"{tag}_sfx.wav"
if not silent.exists():
    subprocess.run(["ffmpeg", "-loglevel", "error", "-n", "-framerate", "24", "-i", str(frames / "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(silent)], check=True)
    print(silent)
else:
    print("exists, kept:", silent)
if wav.exists():
    if sound.exists():
        print("exists, kept:", sound)
    else:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-n", "-i", str(silent), "-i", str(wav), "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", str(sound)], check=True)
        print(sound)
