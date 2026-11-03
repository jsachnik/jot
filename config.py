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
    "sticker_cost": 100,          # price of one sticker
}

# Ideas can be in these states. "open" is the default.
STATUSES = ("open", "worked", "partial", "failed", "shelved")

# --- sticker rolls ----------------------------------------------------------
# A sticker is built from a chain of rolls (see stickerbank.py):
#   noun category -> the specific noun -> how many adjectives -> each adjective's type and which one
#   -> maybe a verb -> maybe puffy / holographic / damage.
# Every roll is weighted, and the "surprise" of the outcomes adds up to a net rarity.
STICKER = {
    # how many adjectives (1 almost always, 3 near impossible)
    "adjective_counts": [0.92, 0.075, 0.005],
    # what kind each adjective is: color, modifier, look, style-of
    "adjective_types": {"color": 0.40, "modifier": 0.35, "look": 0.15, "style_of": 0.10},
    "verb": 0.25,
    # extras, all very rare
    "puffy": 0.005,
    "holographic": 0.004,
    "damage": {"scuffed": 0.003, "ripped": 0.0015, "shredded": 0.0005},   # chance of each tier
    "torn_off": 0.00001,       # the first roll: 0.001% the sticker has been torn right off
    # how common is a noun, from the AI's 1-5 familiarity rating (5 = everyday, 1 = outlandish)
    "familiarity_weight": {5: 100, 4: 50, 3: 20, 2: 6, 1: 1},
    "idea_bias": 0.6,          # chance a sticker made from chosen ideas picks something related to them
    # share of stickers in each rarity tier (common is whatever is left over)
    "tier_shares": {"uncommon": 0.22, "rare": 0.09, "legendary": 0.035, "mythical": 0.005},
}
DAMAGE_NAMES = ["Scuffed", "Ripped", "Shredded", "Torn-Off"]
TIERS = ["COMMON", "UNCOMMON", "RARE", "LEGENDARY", "MYTHICAL"]
