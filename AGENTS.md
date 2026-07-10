# AGENTS.md — ScreenBot

## What this is
Single-file PyQt6 desktop companion app (609 lines). Connects to a local Ollama instance for LLM chat, renders an animated robot widget, persists memory and settings to JSON files in `~`.

## Dependencies

```bash
pip install PyQt6 requests
```

**PyQt6 is not in the current venv** — install it before running.

## How to run

```bash
# Ollama must be running with the model already pulled
ollama pull llama3.2:1b
ollama serve

# Then start the app
python ScreenBot.py
```

If Ollama isn't running, the bot falls back to a static error message: `"My local brain is offline. Make sure Ollama is running."`

## Architecture (all in `ScreenBot.py`)

| Component | Role |
|---|---|
| `ScreenBot(QWidget)` | Main app window. State machine: `idle → thinking → speaking → happy → idle`. Manages layout, timers, lifecycle. |
| `RobotWidget(QWidget)` | Custom-painted animated robot face. States: idle, thinking, sleepy, happy, curious. |
| `StreamWorker(QThread)` | Background thread. Calls `http://localhost:11434/api/generate` with streaming, emits chunks via signals. |
| `SettingsWindow(QWidget)` | Settings popup. Saved to `~/.screenbot_settings.json`. |
| `load_json` / `save_json` | Merged-read + write utilities for JSON persistence. |

**State machine**: idle → (timeout + curiosity threshold → curious/sleepy) OR (user sends message → thinking → speaking → happy → idle).

**Hardcoded model**: `llama3.2:1b` at line 25. No config setting for it.

## Data files (in home directory)

- `~/.screenbot_memory.json` — facts, conversation_count, last_chat, energy, curiosity, social
- `~/.screenbot_settings.json` — theme, background, text_color, timers, memory/thinking levels

## Gotchas

- **No tests, no linter, no formatter, no CI.** Changes must be validated manually by running the app.
- **No `requirements.txt` or `pyproject.toml` exists.** Dependencies are `PyQt6` + `requests`.
- **The `.gitignore` is a Java template** — not useful for this Python project. Don't rely on it.
- **The `ScreenBot/` subdirectory is a stale nested git repo** (only has `.git`, `.gitignore`, `LICENSE` — no code). Do not add files there. The real app is `ScreenBot.py` in the repo root.
- **Memory/learning** is triggered by literal string prefixes: `"remember that"`, `"remember"`, `"i like"`, `"i prefer"`. Facts are capped by `memory_level` setting (5–200 items).
- **The UI uses absolute pixel positioning** via `setGeometry()` — resizing or reordering widgets requires manual coordinate adjustments.
- **`QTimer` intervals**: animation runs at 80ms (~12.5 FPS), life loop at 1000ms (1s). Don't change these without testing the visual feel.
- **Curiosity/sleep timers are in minutes** in the settings UI but converted to seconds internally (`* 60`).
- **Cursor position polling** in `curious` state uses `self.cursor().pos()` relative to widget — may be janky on multi-monitor or high-DPI setups.
