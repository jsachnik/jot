"""Jot settings you may want to tweak. Everything here is plain data.

Labels and colours that the browser shows live in static/config.js and
static/style.css; the offline brainstorming questions live in questions.py;
the prompts sent to an LLM live in prompts.py.
"""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

# Where your ideas live: one SQLite file plus an uploads folder.
DATA_DIR = Path(os.environ.get("JOT_DATA") or APP_DIR / "jot_data")
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "jot.db"

HOST = "127.0.0.1"          # local only. Do not change unless you know why.
PORT = int(os.environ.get("JOT_PORT") or 5057)

MAX_UPLOAD_MB = 50

# --- points -----------------------------------------------------------------
POINTS = {
    "jot": 10,                    # writing a new idea down
    "jot_detail_bonus": 5,        # ...and adding a real description (10+ words)
    "brainstorm_choice": 5,       # picking one of the four options
    "brainstorm_written_base": 10,  # writing your own answer
    "brainstorm_per_word": 1,     # +1 per word, up to the cap
    "brainstorm_written_cap": 30,
    "brainstorm_variety_bonus": 5,  # 15+ different words
    "ai_depth_per_level": 2,      # AI rates depth 1-5 -> up to +8
    "update_base": 20,            # closing the loop on an idea
    "update_section": 5,          # per section (went well / poorly / improve) filled
}

# Ideas can be in these states. "open" is the default.
STATUSES = ("open", "worked", "partial", "failed", "shelved")
