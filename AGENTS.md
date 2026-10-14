# Agent instructions

This repository is an agent skill: **doodle-to-3d** — turn a child's hand drawing into an animated 3D character that
keeps the child's pencil lines, then render flying / fire-breathing scenes with sound effects.

Follow [SKILL.md](SKILL.md) step by step. Setup is in [README.md](README.md) (Japanese) / [README.en.md](README.en.md) (English); the config format is in
[docs/CONFIG.md](docs/CONFIG.md); a worked example is `examples/purple-dragon/config.json`.

Rules that matter most:
- Keep each drawing's work directory outside this repository; never commit drawings, renders or `.env`.
- Read `GEMINI_API_KEY` from the environment / `.env` only; never print or log it.
- Ask the user what ambiguous shapes are before building parts, and tell them before each Gemini call (it costs money
  and uploads the drawing).
- Never overwrite delivered videos or frozen assets; write new variants under new names.
