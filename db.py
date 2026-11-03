"""SQLite storage for Jot."""

import sqlite3
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
  color TEXT NOT NULL DEFAULT '#6c8cff',
  sort INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS ideas(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  x REAL, y REAL,
  created_at TEXT, updated_at TEXT, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS idea_groups(
  idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  PRIMARY KEY(idea_id, group_id)
);
CREATE TABLE IF NOT EXISTS links(
  id INTEGER PRIMARY KEY,
  source INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  target INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'related',   -- related | spawned
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT,
  UNIQUE(source, target, kind)
);
CREATE TABLE IF NOT EXISTS updates(
  id INTEGER PRIMARY KEY,
  idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  outcome TEXT NOT NULL,
  went_well TEXT NOT NULL DEFAULT '',
  went_poorly TEXT NOT NULL DEFAULT '',
  improve TEXT NOT NULL DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS attachments(
  id INTEGER PRIMARY KEY,
  idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  name TEXT NOT NULL, stored TEXT NOT NULL, mime TEXT, size INTEGER,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS brainstorm(
  id INTEGER PRIMARY KEY,
  idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  qkey TEXT, question TEXT NOT NULL, options TEXT NOT NULL, source TEXT,
  choice INTEGER, answer TEXT, points INTEGER NOT NULL DEFAULT 0, depth INTEGER,
  created_at TEXT, answered_at TEXT
);
CREATE TABLE IF NOT EXISTS points(
  id INTEGER PRIMARY KEY,
  amount INTEGER NOT NULL, reason TEXT,
  idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,
  idea_id INTEGER REFERENCES ideas(id) ON DELETE CASCADE,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS stickers(
  id INTEGER PRIMARY KEY,
  name TEXT, svg TEXT NOT NULL, idea_ids TEXT, source TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS ix_events_idea ON events(idea_id);
CREATE INDEX IF NOT EXISTS ix_links_s ON links(source);
CREATE INDEX IF NOT EXISTS ix_links_t ON links(target);
"""

DEFAULT_GROUPS = [
    ("Work", None, "#4f8cff"),
    ("Personal", None, "#f0873c"),
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(stickers)")}
    for col in ("recipe", "rarity"):                 # added after the first release
        if col not in cols:
            conn.execute(f"ALTER TABLE stickers ADD COLUMN {col} TEXT")
    if not conn.execute("SELECT 1 FROM groups LIMIT 1").fetchone():
        for i, (name, parent, color) in enumerate(DEFAULT_GROUPS):
            conn.execute("INSERT INTO groups(name,parent_id,color,sort,created_at) VALUES(?,?,?,?,?)",
                         (name, parent, color, i, now()))
    conn.commit()
    conn.close()


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def add_event(conn, type_, idea_id=None, detail=""):
    conn.execute("INSERT INTO events(type,idea_id,detail,created_at) VALUES(?,?,?,?)",
                 (type_, idea_id, detail, now()))


def add_points(conn, amount, reason, idea_id=None):
    if amount:
        conn.execute("INSERT INTO points(amount,reason,idea_id,created_at) VALUES(?,?,?,?)",
                     (amount, reason, idea_id, now()))


def total_points(conn):
    return conn.execute("SELECT COALESCE(SUM(amount),0) FROM points").fetchone()[0]
