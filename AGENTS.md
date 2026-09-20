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

## Single instance & recovery

- `main.py` refuses to launch a second Bob: if another ScreenBot process is
  already running, a KDE notification `"Bob is already running 🤖"` is sent and
  an in-app dialog offers the same two choices:
  - **Clean up old Bobs and continue launching ScreenBot** — shows a progress
    bar on the startup window, SIGTERMs the old Bobs, escalates to SIGKILL if
    any survive, then continues launching normally.
  - **Show the running Bob** — asks the existing Bob to reveal its window (via
    `~/.screenbot_show_request`) and exits. A second Bob is never started, so
    Bob cannot duplicate.
- If the notification is dismissed or expires before a choice, the new process
  exits without launching anything — a duplicate Bob is never created.
- Closing Bob asks "Want to keep ScreenBot on or off?" via the same
  notification + dialog pair. **Yes, keep it open and close screenbot** closes
  the window but keeps the ScreenBot process alive in the background with light
  activity (no scanning, walking, or autonomous chat); **No, kill it.** closes
  the walking host and quits the process. Dismissing the prompt cancels the
  close.
- The Settings window's **Background mode** (On/Off) enables or disables that
  background option. With **Off**, choosing "Yes, keep it open..." simply
  cancels the close and Bob stays open — the server is never left running
  without a window. While a Bob runs in the background, nothing may re-show its
  UI (late autonomous replies are notified but never reopen the window).
- pkill is not used automatically from inside the app; cleanup only runs when
  the user clicks the cleanup button. Stuck old processes can also be recovered
  manually:

```bash
pkill -f '/home/boda/ScreenBot/main.py'
pkill -f '/home/boda/ScreenBot/ScreenBot.py'
pgrep -af 'ScreenBot|main.py'                    # verify all Bobs are dead
pkill -9 -f '/home/boda/ScreenBot/main.py'       # escalate only if some survive
pkill -9 -f '/home/boda/ScreenBot/ScreenBot.py'
```

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
- `~/.screenbot_chats.json` — saved chats (id, title, messages, timestamps) with the active chat id

## Chats and thinking mode

- The expanded window has a chat sidebar: **New chat**, **Search chats**, the chat
  list (newest first, scrollable), and **⋯ Rename** (also via right-click on a chat).
- Every chat is saved to `~/.screenbot_chats.json`; switching chats reloads that
  chat's messages and its LLM context.
- New chats are auto-named: a quick local fallback title appears immediately, then
  the brain replaces it with a proper title (correct capitalization for company,
  product, and proper-noun names). A manual rename always wins.
- The **⋯** menu in the chat sidebar both **renames** and **deletes** a chat
  (delete asks for confirmation, then activates the newest remaining chat).
- The **thinking** picker beside the message box mirrors the Settings window's
  `thinking_level` and persists to `~/.screenbot_settings.json`.
- The Settings window's **Text size** (Small / Medium / Large / Extra Large)
  scales the whole UI font and persists as `text_size`.

## Screen capture (vision)

- `world/vision.py` captures the screen through the **XDG Desktop Portal**
  (`org.freedesktop.portal.Screenshot` → KWin `ScreenShot2`), never through the
  Spectacle CLI. The old `spectacle -b -n -f -o …` call took over the
  `org.kde.Spectacle` bus name, which made systemd kill the user's open
  Spectacle window within seconds.
- The portal asks for permission once per app; once granted, captures take
  ~0.3 s. `PORTAL_TIMEOUT_MS` bounds a stuck request and a failed capture
  returns `None`, so the scan loop skips that cycle instead of hanging.
- The portal writes the image into `~/Pictures` and returns a `file://` URI;
  ScreenBot copies it into its own temp file and deletes the original.

## Walking host (Wayland)

- `world/walking_host.py` hosts Bob in a **full-screen** frameless always-on-top
  window and moves Bob *inside* it. Wayland does not let a client position its
  own top-level window, so moving the host window (`move()`) does nothing —
  Bob must be repositioned within the full-screen surface.
- The host is masked to Bob's rect so the rest of the screen stays clickable.
  Because a mask clips painting, the area Bob just left can never be cleared on
  its own — that is what left "ghost" copies of Bob at his previous positions.
  `move_bob()` therefore widens the mask to `old ∪ new`, repaints that region
  (the host's `paintEvent` clears it to transparent with `CompositionMode_Source`),
  then shrinks the mask back to Bob's new rect.

## Control panel

- `world/control_panel.py` is a **single neon button** (`•••`) that can be
  **dragged anywhere** on screen — it is a child of the walking host, so moving
  it works on Wayland where windows cannot be positioned. Clicking it opens a
  menu titled with the bot's name containing **Sleep / Idle / Big**.
- Settings: **Button shape** (`panel_shape`: Circle / Square / Rectangle /
  Triangle) and **Auto move** (`panel_auto_move`: On / Off). Shapes resize the
  button (46×46, 46×46, 72×40, 54×46) and the host mask follows.
- Dropping the button **pins** it (`panel_manual`). With **Auto move = On** and
  no pin it glides to scan-chosen blank spots with `MovementEngine`
  (`speed = 2` px/30 ms tick); saving settings with Auto move On releases a pin,
  and with Auto move Off the scan never moves it.
- It is part of the host's mask; `geometry_changed` re-applies the mask while
  dragging so the area it leaves is cleared.
- On every awareness scan the worker also picks a blank spot for the panel
  (`ParkingWorker.find_panel_spot`) using the same OCR/visual scoring, with
  Bob's destination passed as `exclude_rect` so the panel never covers him. The
  scan image is reused (no second OCR pass).
- Settings: **Panel color** (`panel_color`, one of the accent colors) styles
  the panel, and **Name** (`bot_name`) replaces "Bob" in prompts, console
  output and chat speaker labels.

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
