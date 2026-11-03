"""Jot: a place to jot ideas down and watch them connect.

Run:  python app.py      (or double-click run.bat)
"""

import io
import json
import mimetypes
import os
import random
import re
import shutil
import threading
import uuid
import webbrowser
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

import config
import db
import llm
import prompts
import questions
import textsim

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
P = config.POINTS


# --- helpers ----------------------------------------------------------------

def conn_():
    return db.connect()


def rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def words(text):
    return re.findall(r"[^\W_]+", text or "")


def err(msg, code=400):
    return jsonify({"error": msg}), code


def ai_ready(conn):
    return llm.describe()["configured"] and db.get_setting(conn, "use_ai", "1") != "0"


def group_map(conn):
    return {g["id"]: g for g in rows(conn, "SELECT * FROM groups")}


def group_path(gmap, gid):
    parts = []
    seen = set()
    while gid and gid in gmap and gid not in seen:
        seen.add(gid)
        parts.append(gmap[gid]["name"])
        gid = gmap[gid]["parent_id"]
    return " \u203a ".join(reversed(parts))


def idea_groups(conn):
    out = {}
    for r in conn.execute("SELECT idea_id, group_id FROM idea_groups"):
        out.setdefault(r["idea_id"], []).append(r["group_id"])
    return out


def set_idea_groups(conn, idea_id, group_ids):
    conn.execute("DELETE FROM idea_groups WHERE idea_id=?", (idea_id,))
    valid = {r["id"] for r in conn.execute("SELECT id FROM groups")}
    for gid in {int(g) for g in group_ids or [] if str(g).lstrip("-").isdigit()}:
        if gid in valid:
            conn.execute("INSERT INTO idea_groups(idea_id,group_id) VALUES(?,?)", (idea_id, gid))


def create_idea(conn, title, body="", group_ids=(), parent_id=None, reason="jot", detail=""):
    title = (title or "").strip()
    if not title:
        raise ValueError("An idea needs a few words.")
    t = db.now()
    cur = conn.execute("INSERT INTO ideas(title,body,status,created_at,updated_at) VALUES(?,?,?,?,?)",
                       (title[:300], (body or "").strip(), "open", t, t))
    iid = cur.lastrowid
    set_idea_groups(conn, iid, group_ids)
    if parent_id:
        conn.execute("INSERT OR IGNORE INTO links(source,target,kind,created_at) VALUES(?,?,?,?)",
                     (parent_id, iid, "spawned", t))
    pts = P["jot"] + (P["jot_detail_bonus"] if len(words(body)) >= 10 else 0)
    db.add_points(conn, pts, "Jotted an idea", iid)
    db.add_event(conn, "jot", iid, detail)
    return iid, pts


_index_cache = {"sig": None, "index": None, "suggest": None}
_index_lock = threading.Lock()


def build_index(conn):
    sig = (tuple(conn.execute("SELECT COUNT(*), COALESCE(MAX(updated_at),''), COALESCE(MAX(id),0) FROM ideas").fetchone()),
           conn.execute("SELECT COUNT(*) FROM updates").fetchone()[0],
           conn.execute("SELECT COUNT(*) FROM idea_groups").fetchone()[0],
           conn.execute("SELECT COUNT(*) FROM links").fetchone()[0])
    with _index_lock:
        if _index_cache["sig"] == sig:
            return _index_cache["index"], _index_cache["suggest"]
        gmap = group_map(conn)
        ig = idea_groups(conn)
        upd = {}
        for u in conn.execute("SELECT idea_id, went_well, went_poorly, improve FROM updates"):
            upd.setdefault(u["idea_id"], []).append(f"{u['went_well']} {u['went_poorly']} {u['improve']}")
        docs = {}
        for r in conn.execute("SELECT id, title, body FROM ideas"):
            gnames = " ".join(gmap[g]["name"] for g in ig.get(r["id"], []) if g in gmap)
            docs[r["id"]] = f"{r['title']} {r['title']} {r['title']} {r['body']} {' '.join(upd.get(r['id'], []))} {gnames}"
        index = textsim.Index(docs)
        linked = {(l["source"], l["target"]) for l in conn.execute("SELECT source,target FROM links")}
        linked |= {(b, a) for a, b in linked}
        suggest, seen = [], set()
        if len(docs) <= 1500:
            for i in docs:
                for j, s in index.similar(i, 2):
                    key = tuple(sorted((i, j)))
                    if s >= 0.3 and (i, j) not in linked and key not in seen:
                        seen.add(key)
                        suggest.append({"source": key[0], "target": key[1], "score": round(s, 2)})
        _index_cache.update(sig=sig, index=index, suggest=suggest)
        return index, suggest


# --- pages ------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/files/<path:name>")
def files(name):
    resp = send_from_directory(config.UPLOAD_DIR, name)
    resp.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# --- bootstrap data ---------------------------------------------------------

@app.route("/api/all")
def api_all():
    conn = conn_()
    ig = idea_groups(conn)
    counts = {}
    for table, key in (("updates", "n_updates"), ("attachments", "n_files")):
        for r in conn.execute(f"SELECT idea_id, COUNT(*) c FROM {table} GROUP BY idea_id"):
            counts.setdefault(r["idea_id"], {})[key] = r["c"]
    for r in conn.execute("SELECT idea_id, COUNT(*) c FROM brainstorm WHERE answered_at IS NOT NULL GROUP BY idea_id"):
        counts.setdefault(r["idea_id"], {})["n_brain"] = r["c"]
    ideas = []
    for r in conn.execute("SELECT * FROM ideas ORDER BY id"):
        d = dict(r)
        body = d.pop("body") or ""
        d["snippet"] = body[:160]
        d["n_notes"] = len(body)
        d["groups"] = ig.get(d["id"], [])
        d.update({"n_updates": 0, "n_files": 0, "n_brain": 0}, **counts.get(d["id"], {}))
        ideas.append(d)
    out = {
        "groups": rows(conn, "SELECT * FROM groups ORDER BY sort, id"),
        "ideas": ideas,
        "links": rows(conn, "SELECT id, source, target, kind, note FROM links"),
        "suggested": build_index(conn)[1],
        "points": db.total_points(conn),
        "ai": dict(llm.describe(), enabled=db.get_setting(conn, "use_ai", "1") != "0"),
        "costs": {"jot": P["jot"]},
    }
    conn.close()
    return jsonify(out)


# --- groups -----------------------------------------------------------------

@app.route("/api/groups", methods=["POST"])
def groups_create():
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    if not name:
        return err("A group needs a name.")
    conn = conn_()
    parent = d.get("parent_id") or None
    n = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    palette = ["#4f8cff", "#f0873c", "#2fb87a", "#b36bf0", "#e5527a", "#d9b92e", "#2fb8c4", "#8b8f9a"]
    cur = conn.execute("INSERT INTO groups(name,parent_id,color,sort,created_at) VALUES(?,?,?,?,?)",
                       (name[:80], parent, d.get("color") or palette[n % len(palette)], n, db.now()))
    conn.commit()
    gid = cur.lastrowid
    conn.close()
    return jsonify({"id": gid})


@app.route("/api/groups/<int:gid>", methods=["PATCH", "DELETE"])
def groups_edit(gid):
    conn = conn_()
    g = conn.execute("SELECT * FROM groups WHERE id=?", (gid,)).fetchone()
    if not g:
        conn.close()
        return err("No such group.", 404)
    if request.method == "DELETE":
        conn.execute("UPDATE groups SET parent_id=? WHERE parent_id=?", (g["parent_id"], gid))
        conn.execute("DELETE FROM groups WHERE id=?", (gid,))
    else:
        d = request.get_json(force=True)
        if "name" in d and d["name"].strip():
            conn.execute("UPDATE groups SET name=? WHERE id=?", (d["name"].strip()[:80], gid))
        if "color" in d:
            conn.execute("UPDATE groups SET color=? WHERE id=?", (d["color"], gid))
        if "parent_id" in d:
            pid = d["parent_id"] or None
            # refuse to make a group its own ancestor
            cur, ok = pid, True
            while cur:
                if cur == gid:
                    ok = False
                    break
                row = conn.execute("SELECT parent_id FROM groups WHERE id=?", (cur,)).fetchone()
                cur = row["parent_id"] if row else None
            if ok:
                conn.execute("UPDATE groups SET parent_id=? WHERE id=?", (pid, gid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# --- ideas ------------------------------------------------------------------

@app.route("/api/ideas", methods=["POST"])
def ideas_create():
    d = request.get_json(force=True)
    conn = conn_()
    try:
        iid, pts = create_idea(conn, d.get("title"), d.get("body", ""), d.get("group_ids"))
    except ValueError as e:
        conn.close()
        return err(str(e))
    conn.commit()
    total = db.total_points(conn)
    conn.close()
    return jsonify({"id": iid, "points": pts, "total": total})


@app.route("/api/ideas/<int:iid>", methods=["GET", "PATCH", "DELETE"])
def idea_one(iid):
    conn = conn_()
    idea = conn.execute("SELECT * FROM ideas WHERE id=?", (iid,)).fetchone()
    if not idea:
        conn.close()
        return err("No such idea.", 404)

    if request.method == "DELETE":
        names = [a["stored"] for a in conn.execute("SELECT stored FROM attachments WHERE idea_id=?", (iid,))]
        conn.execute("DELETE FROM ideas WHERE id=?", (iid,))
        conn.commit()
        conn.close()
        for n in names:
            try:
                (config.UPLOAD_DIR / n).unlink()
            except OSError:
                pass
        return jsonify({"ok": True})

    if request.method == "PATCH":
        d = request.get_json(force=True)
        t = db.now()
        if "title" in d and d["title"].strip():
            conn.execute("UPDATE ideas SET title=?, updated_at=? WHERE id=?", (d["title"].strip()[:300], t, iid))
        if "body" in d and d["body"] != idea["body"]:
            conn.execute("UPDATE ideas SET body=?, updated_at=? WHERE id=?", (d["body"], t, iid))
            last = conn.execute("SELECT created_at FROM events WHERE idea_id=? AND type='note' ORDER BY id DESC LIMIT 1",
                                (iid,)).fetchone()
            recent = False
            if last:
                from datetime import datetime
                recent = (datetime.fromisoformat(t) - datetime.fromisoformat(last["created_at"])).total_seconds() < 1800
            if not recent:
                db.add_event(conn, "note", iid, "Wrote notes")
        if "group_ids" in d:
            set_idea_groups(conn, iid, d["group_ids"])
            conn.execute("UPDATE ideas SET updated_at=? WHERE id=?", (t, iid))
        if "status" in d and d["status"] in config.STATUSES:
            conn.execute("UPDATE ideas SET status=?, updated_at=? WHERE id=?", (d["status"], t, iid))
        if "x" in d and "y" in d:
            conn.execute("UPDATE ideas SET x=?, y=? WHERE id=?", (d["x"], d["y"], iid))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    out = dict(idea)
    out["groups"] = [r["group_id"] for r in conn.execute("SELECT group_id FROM idea_groups WHERE idea_id=?", (iid,))]
    out["attachments"] = rows(conn, "SELECT * FROM attachments WHERE idea_id=? ORDER BY id", (iid,))
    out["updates"] = rows(conn, "SELECT * FROM updates WHERE idea_id=? ORDER BY id", (iid,))
    out["brainstorm"] = [dict(r, options=json.loads(r["options"])) for r in
                         conn.execute("SELECT * FROM brainstorm WHERE idea_id=? AND answered_at IS NOT NULL ORDER BY id", (iid,))]
    out["links"] = rows(conn, """
        SELECT l.id, l.kind, l.note, l.source, l.target,
               CASE WHEN l.source=? THEN l.target ELSE l.source END AS other_id,
               o.title AS other_title, o.status AS other_status
        FROM links l JOIN ideas o ON o.id = CASE WHEN l.source=? THEN l.target ELSE l.source END
        WHERE l.source=? OR l.target=?""", (iid, iid, iid, iid))
    conn.close()
    return jsonify(out)


# --- links ------------------------------------------------------------------

@app.route("/api/links", methods=["POST"])
def links_create():
    d = request.get_json(force=True)
    try:
        a, b = int(d["source"]), int(d["target"])
    except (KeyError, ValueError, TypeError):
        return err("Need source and target.")
    kind = d.get("kind") if d.get("kind") in ("related", "spawned") else "related"
    if a == b:
        return err("An idea can't link to itself.")
    conn = conn_()
    exists = conn.execute("SELECT 1 FROM links WHERE (source=? AND target=?) OR (source=? AND target=?)",
                          (a, b, b, a)).fetchone()
    if exists:
        conn.close()
        return err("Those two ideas are already connected.")
    try:
        conn.execute("INSERT INTO links(source,target,kind,note,created_at) VALUES(?,?,?,?,?)",
                     (a, b, kind, (d.get("note") or "")[:300], db.now()))
    except Exception:
        conn.close()
        return err("Could not link those ideas.")
    db.add_event(conn, "link", a, "Connected to another idea")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/links/<int:lid>", methods=["DELETE"])
def links_delete(lid):
    conn = conn_()
    conn.execute("DELETE FROM links WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# --- updates (closing the loop) ---------------------------------------------

@app.route("/api/ideas/<int:iid>/update", methods=["POST"])
def idea_update(iid):
    d = request.get_json(force=True)
    outcome = d.get("outcome")
    if outcome not in config.STATUSES or outcome == "open":
        return err("Pick how it went.")
    conn = conn_()
    idea = conn.execute("SELECT * FROM ideas WHERE id=?", (iid,)).fetchone()
    if not idea:
        conn.close()
        return err("No such idea.", 404)
    t = db.now()
    well, poor, imp = ((d.get(k) or "").strip() for k in ("went_well", "went_poorly", "improve"))
    conn.execute("INSERT INTO updates(idea_id,outcome,went_well,went_poorly,improve,created_at) VALUES(?,?,?,?,?,?)",
                 (iid, outcome, well, poor, imp, t))
    conn.execute("UPDATE ideas SET status=?, closed_at=?, updated_at=? WHERE id=?", (outcome, t, t, iid))
    db.add_event(conn, "update", iid, outcome)
    pts = P["update_base"] + sum(P["update_section"] for s in (well, poor, imp) if len(words(s)) >= 3)
    db.add_points(conn, pts, "Gave an update", iid)
    inherit = [r["group_id"] for r in conn.execute("SELECT group_id FROM idea_groups WHERE idea_id=?", (iid,))]
    spawned = []
    for title in d.get("spawn") or []:
        if title and title.strip():
            nid, p = create_idea(conn, title, "", inherit, parent_id=iid, detail="Spawned from another idea")
            pts += p
            spawned.append(nid)
    conn.commit()
    total = db.total_points(conn)
    conn.close()
    return jsonify({"points": pts, "total": total, "spawned": spawned})


# --- attachments ------------------------------------------------------------

@app.route("/api/ideas/<int:iid>/attachments", methods=["POST"])
def attach(iid):
    f = request.files.get("file")
    if not f or not f.filename:
        return err("No file received.")
    conn = conn_()
    if not conn.execute("SELECT 1 FROM ideas WHERE id=?", (iid,)).fetchone():
        conn.close()
        return err("No such idea.", 404)
    name = secure_filename(f.filename) or "file"
    stored = f"{uuid.uuid4().hex[:10]}_{name}"
    path = config.UPLOAD_DIR / stored
    f.save(path)
    mime = f.mimetype if f.mimetype and f.mimetype != "application/octet-stream" else (mimetypes.guess_type(name)[0] or "application/octet-stream")
    cur = conn.execute("INSERT INTO attachments(idea_id,name,stored,mime,size,created_at) VALUES(?,?,?,?,?,?)",
                       (iid, f.filename[:200], stored, mime, path.stat().st_size, db.now()))
    db.add_event(conn, "attach", iid, f.filename[:200])
    conn.commit()
    out = {"id": cur.lastrowid, "name": f.filename, "stored": stored, "mime": mime, "url": f"/files/{stored}"}
    conn.close()
    return jsonify(out)


@app.route("/api/attachments/<int:aid>", methods=["DELETE"])
def attach_delete(aid):
    conn = conn_()
    row = conn.execute("SELECT stored FROM attachments WHERE id=?", (aid,)).fetchone()
    if row:
        conn.execute("DELETE FROM attachments WHERE id=?", (aid,))
        conn.commit()
        try:
            (config.UPLOAD_DIR / row["stored"]).unlink()
        except OSError:
            pass
    conn.close()
    return jsonify({"ok": True})


# --- brainstorming ----------------------------------------------------------

def _offline_question(conn, iid, title):
    asked = [r["qkey"] for r in conn.execute("SELECT qkey FROM brainstorm WHERE idea_id=? ORDER BY id", (iid,))]
    fresh = [q for q in questions.QUESTIONS if q[0] not in asked]
    if fresh:
        key, text, opts = random.choice(fresh)
    else:  # asked them all: take the one asked longest ago
        key = next(k for k in asked if k in {q[0] for q in questions.QUESTIONS})
        key, text, opts = next(q for q in questions.QUESTIONS if q[0] == key)
    return key, text.replace("{idea}", title), list(opts)


@app.route("/api/ideas/<int:iid>/brainstorm/next", methods=["POST"])
def brainstorm_next(iid):
    d = request.get_json(silent=True) or {}
    conn = conn_()
    idea = conn.execute("SELECT * FROM ideas WHERE id=?", (iid,)).fetchone()
    if not idea:
        conn.close()
        return err("No such idea.", 404)
    notice, bonus = "", 0
    source, key = "offline", None
    question = opts = None
    if ai_ready(conn):
        try:
            history = rows(conn, "SELECT id, question, choice, answer, depth FROM brainstorm "
                                 "WHERE idea_id=? AND answered_at IS NOT NULL ORDER BY id DESC LIMIT 8", (iid,))[::-1]
            ctx = [f"IDEA: {idea['title']}"]
            if idea["body"]:
                ctx.append(f"THEIR NOTES: {idea['body'][:1500]}")
            for u in conn.execute("SELECT * FROM updates WHERE idea_id=?", (iid,)):
                ctx.append(f"RESULT ({u['outcome']}): {u['went_well']} {u['went_poorly']} {u['improve']}"[:500])
            gm = group_map(conn)
            g = [group_path(gm, r["group_id"]) for r in conn.execute("SELECT group_id FROM idea_groups WHERE idea_id=?", (iid,))]
            if g:
                ctx.append("GROUPS: " + "; ".join(g))
            index, _ = build_index(conn)
            rel = [r["title"] for r in (conn.execute("SELECT title FROM ideas WHERE id=?", (j,)).fetchone()
                                        for j, _ in index.similar(iid, 4))]
            if rel:
                ctx.append("THEIR OTHER RELATED IDEAS: " + "; ".join(rel))
            if history:
                ctx.append("EARLIER Q&A:\n" + "\n".join(f"Q: {h['question']}\nA: {h['answer']}" for h in history))
            prev = history[-1] if history and history[-1]["id"] == d.get("prev_id") else None
            if prev:
                ctx.append(f"THE ANSWER TO RATE (the last one above): {prev['answer']}")
            data = llm.chat_json([{"role": "system", "content": prompts.BRAINSTORM_SYSTEM},
                                  {"role": "user", "content": "\n".join(ctx)}])
            q, o = str(data.get("question") or "").strip(), [str(x).strip() for x in data.get("options") or [] if str(x).strip()]
            if not q or len(o) < 4:
                raise ValueError("The AI didn't return a question with four options.")
            question, opts, source = q, o[:4], "ai"
            depth = data.get("prev_depth")
            if prev and isinstance(depth, (int, float)) and 1 <= depth <= 5 and prev.get("depth") is None:
                bonus = int(round(depth - 1)) * P["ai_depth_per_level"]
                conn.execute("UPDATE brainstorm SET depth=?, points=points+? WHERE id=?", (int(depth), bonus, prev["id"]))
                db.add_points(conn, bonus, "Depth bonus", iid)
        except Exception as exc:  # noqa: BLE001 - never leave the user without a question
            notice = f"The AI couldn't be reached, so here is a guided prompt instead. ({str(exc)[:120]})"
    if not question:
        key, question, opts = _offline_question(conn, iid, idea["title"])
    cur = conn.execute("INSERT INTO brainstorm(idea_id,qkey,question,options,source,created_at) VALUES(?,?,?,?,?,?)",
                       (iid, key, question, json.dumps(opts), source, db.now()))
    conn.commit()
    out = {"id": cur.lastrowid, "question": question, "options": opts, "source": source,
           "notice": notice, "bonus": bonus, "total": db.total_points(conn)}
    conn.close()
    return jsonify(out)


@app.route("/api/brainstorm/<int:qid>/answer", methods=["POST"])
def brainstorm_answer(qid):
    d = request.get_json(force=True)
    conn = conn_()
    q = conn.execute("SELECT * FROM brainstorm WHERE id=?", (qid,)).fetchone()
    if not q or q["answered_at"]:
        conn.close()
        return err("That question was already answered.")
    opts = json.loads(q["options"])
    choice = d.get("choice")
    text = (d.get("text") or "").strip()
    if isinstance(choice, int) and 0 <= choice < len(opts):
        answer, pts, note = opts[choice], P["brainstorm_choice"], "Thanks!"
    else:
        if not text:
            conn.close()
            return err("Write a few words, or pick one of the options.")
        w = words(text)
        pts = P["brainstorm_written_base"] + min(len(w) * P["brainstorm_per_word"], P["brainstorm_written_cap"])
        if len({x.lower() for x in w}) >= 15:
            pts += P["brainstorm_variety_bonus"]
        answer, choice = text, 4
        note = "Great depth!" if pts >= 30 else "Nice, thanks for expanding."
    conn.execute("UPDATE brainstorm SET choice=?, answer=?, points=?, answered_at=? WHERE id=?",
                 (choice, answer, pts, db.now(), qid))
    db.add_points(conn, pts, "Brainstormed", q["idea_id"])
    db.add_event(conn, "brainstorm", q["idea_id"], q["question"][:200])
    conn.execute("UPDATE ideas SET updated_at=? WHERE id=?", (db.now(), q["idea_id"]))
    conn.commit()
    total = db.total_points(conn)
    conn.close()
    return jsonify({"points": pts, "note": note, "total": total})


# --- suggestions & librarian ------------------------------------------------

def _catalog(conn, limit=300, focus=None):
    gm, ig = group_map(conn), idea_groups(conn)
    allrows = rows(conn, "SELECT id, title, body, status FROM ideas ORDER BY id DESC")
    if len(allrows) > limit and focus:
        idx, _ = build_index(conn)
        keep = {i for i, _ in idx.query(focus, 120)} | {r["id"] for r in allrows[:60]}
        allrows = [r for r in allrows if r["id"] in keep]
    lines = []
    for r in allrows[:limit]:
        gs = ", ".join(group_path(gm, g) for g in ig.get(r["id"], [])) or "ungrouped"
        snip = re.sub(r"\s+", " ", r["body"])[:140]
        lines.append(f"{r['id']} | {r['status']} | {gs} | {r['title']} | {snip}")
    return "\n".join(lines), {r["id"] for r in allrows}


@app.route("/api/ideas/<int:iid>/suggest")
def suggest(iid):
    conn = conn_()
    idea = conn.execute("SELECT * FROM ideas WHERE id=?", (iid,)).fetchone()
    if not idea:
        conn.close()
        return err("No such idea.", 404)
    linked = {r["o"] for r in conn.execute(
        "SELECT CASE WHEN source=? THEN target ELSE source END o FROM links WHERE source=? OR target=?", (iid, iid, iid))}
    index, _ = build_index(conn)
    titles = {r["id"]: r["title"] for r in conn.execute("SELECT id, title FROM ideas")}
    out = []
    if request.args.get("mode") == "ai":
        if not ai_ready(conn):
            conn.close()
            return err("AI isn't turned on. Use the keyword suggestions, or see the README to connect an LLM.")
        cat, valid = _catalog(conn, 250, idea["title"])
        try:
            data = llm.chat_json([{"role": "system", "content": prompts.CONNECT_SYSTEM},
                                  {"role": "user", "content": f"THE IDEA: {idea['title']}\n{idea['body'][:1200]}\n\nCATALOG:\n{cat}"}])
        except Exception as exc:  # noqa: BLE001
            conn.close()
            return err(f"The AI couldn't answer: {str(exc)[:160]}", 502)
        for m in data.get("links") or []:
            try:
                j = int(m.get("id"))
            except (TypeError, ValueError):
                continue
            if j in valid and j != iid and j not in linked and j in titles:
                out.append({"id": j, "title": titles[j], "why": str(m.get("why") or "")[:200], "source": "ai"})
    else:
        for j, s in index.similar(iid, 8):
            if j not in linked:
                sw = ", ".join(index.shared_words(iid, j))
                out.append({"id": j, "title": titles[j], "why": f"Shares: {sw}" if sw else "Similar wording", "source": "keywords", "score": round(s, 2)})
    conn.close()
    return jsonify({"suggestions": out})


@app.route("/api/librarian", methods=["POST"])
def librarian():
    d = request.get_json(force=True)
    q = (d.get("question") or "").strip()
    if not q:
        return err("Ask the librarian something.")
    conn = conn_()
    gm, ig = group_map(conn), idea_groups(conn)
    info = {r["id"]: r for r in rows(conn, "SELECT id, title, status FROM ideas")}
    if not info:
        conn.close()
        return jsonify({"answer": "Your collection is empty so far, so anything you jot down will be new.",
                        "verdict": "new", "matches": [], "source": "offline"})
    index, _ = build_index(conn)
    notice = ""

    def shape(i, why):
        return {"id": i, "title": info[i]["title"], "status": info[i]["status"], "why": why,
                "groups": [group_path(gm, g) for g in ig.get(i, [])]}

    if ai_ready(conn):
        try:
            cat, valid = _catalog(conn, 300, q)
            msgs = [{"role": "system", "content": prompts.LIBRARIAN_SYSTEM}]
            for h in (d.get("history") or [])[-4:]:
                msgs.append({"role": "user" if h.get("role") == "user" else "assistant", "content": str(h.get("text"))[:1500]})
            msgs.append({"role": "user", "content": f"CATALOG:\n{cat}\n\nQUESTION: {q}"})
            data = llm.chat_json(msgs)
            matches = []
            for m in data.get("matches") or []:
                try:
                    i = int(m.get("id"))
                except (TypeError, ValueError):
                    continue
                if i in info and i in valid and all(x["id"] != i for x in matches):
                    matches.append(shape(i, str(m.get("why") or "")[:200]))
            verdict = data.get("verdict") if data.get("verdict") in ("new", "covered", "extend", "browse") else "browse"
            conn.close()
            return jsonify({"answer": str(data.get("answer") or "").strip() or "Here is what I found.",
                            "verdict": verdict, "matches": matches[:8], "source": "ai"})
        except Exception as exc:  # noqa: BLE001
            notice = f"(The AI couldn't be reached, so I searched by keywords instead: {str(exc)[:100]})"

    hits = index.query(q, 8)
    matches = []
    for i, s in hits:
        matches.append(shape(i, f"Keyword match ({int(min(s, 1) * 100)}%)"))
    top = hits[0][1] if hits else 0
    if not hits:
        verdict, ans = "new", "I couldn't find anything that looks related. This seems like a new idea. Worth jotting down!"
    else:
        first = matches[0]
        where = f" in {first['groups'][0]}" if first["groups"] else ""
        if top >= 0.55:
            verdict = "covered"
            ans = f"This looks mostly covered already: \u201c{first['title']}\u201d{where} says something very similar. Maybe add to it instead of creating a new one."
        elif top >= 0.25:
            verdict = "extend"
            ans = f"I found {len(matches)} related idea{'s' if len(matches) != 1 else ''}. The closest is \u201c{first['title']}\u201d{where}. This might extend it, or deserve its own Jot connected to it."
        else:
            verdict = "new"
            ans = f"Only loosely related ideas turned up (closest: \u201c{first['title']}\u201d{where}). This is probably a new Jot."
    conn.close()
    return jsonify({"answer": (ans + " " + notice).strip(), "verdict": verdict, "matches": matches, "source": "offline"})


# --- timeline ---------------------------------------------------------------

@app.route("/api/events")
def events():
    conn = conn_()
    ig = idea_groups(conn)
    out = []
    for r in conn.execute("""SELECT e.id, e.type, e.idea_id, e.detail, e.created_at, i.title, i.status
                             FROM events e LEFT JOIN ideas i ON i.id = e.idea_id
                             ORDER BY e.id DESC LIMIT 3000"""):
        d = dict(r)
        d["groups"] = ig.get(d["idea_id"], [])
        out.append(d)
    conn.close()
    return jsonify(out)


# --- settings, AI test, backup ----------------------------------------------

@app.route("/api/settings", methods=["POST"])
def settings_save():
    d = request.get_json(force=True)
    conn = conn_()
    if "use_ai" in d:
        db.set_setting(conn, "use_ai", "1" if d["use_ai"] else "0")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/llm/test", methods=["POST"])
def llm_test():
    try:
        reply = llm.chat("Reply with exactly: ok", timeout=60)
        return jsonify({"ok": True, "reply": reply[:80], "label": llm.describe()["label"]})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)[:300]})


TABLES = ["groups", "ideas", "idea_groups", "links", "updates", "attachments", "brainstorm", "points", "events", "settings"]


@app.route("/api/export")
def export():
    conn = conn_()
    data = {t: rows(conn, f"SELECT * FROM {t}") for t in TABLES}
    conn.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", json.dumps({"jot_backup": 1, "tables": data}))
        for p in config.UPLOAD_DIR.glob("*"):
            if p.is_file():
                z.write(p, f"uploads/{p.name}")
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"jot-backup-{db.now()[:10]}.zip")


@app.route("/api/import", methods=["POST"])
def import_():
    f = request.files.get("file")
    if not f:
        return err("Choose a backup .zip.")
    try:
        z = zipfile.ZipFile(f.stream)
        payload = json.loads(z.read("data.json"))
        tables = payload["tables"]
    except Exception:  # noqa: BLE001
        return err("That doesn't look like a Jot backup.")
    conn = conn_()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for t in reversed(TABLES):
            conn.execute(f"DELETE FROM {t}")
        for t in TABLES:
            cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({t})")]
            for row in tables.get(t, []):
                use = [c for c in cols if c in row]
                conn.execute(f"INSERT INTO {t}({','.join(use)}) VALUES({','.join('?' * len(use))})", [row[c] for c in use])
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        conn.close()
        return err(f"Import failed, nothing was changed: {exc}")
    conn.close()
    for info in z.infolist():
        if info.filename.startswith("uploads/") and not info.is_dir():
            name = secure_filename(Path(info.filename).name)
            if name:
                with z.open(info) as src, open(config.UPLOAD_DIR / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return jsonify({"ok": True})


@app.after_request
def no_cache(resp):
    if request.path.startswith(("/api/", "/static/")) or request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


def main():
    db.init()
    url = f"http://{config.HOST}:{config.PORT}/"
    print(f"Jot is running at {url}\nLeave this window open while you use it. Press Ctrl+C to stop.")
    d = llm.describe()
    print("AI:", d["label"] if d["configured"] else "offline mode (see README to connect an LLM)")
    if not os.environ.get("JOT_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
