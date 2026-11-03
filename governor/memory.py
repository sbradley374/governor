"""Local per-person facts and summaries; no raw recordings or camera frames."""
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Memory:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        path = directory / "governor.sqlite3"
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS people (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL,
          turns INTEGER NOT NULL DEFAULT 0, last_seen TEXT);
        CREATE TABLE IF NOT EXISTS facts (
          id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
          text TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS faces (
          person_id TEXT PRIMARY KEY REFERENCES people(id) ON DELETE CASCADE,
          embedding TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS episodes (
          id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
          text TEXT NOT NULL, created TEXT NOT NULL);
        """)
        # Additive migration preserves existing profiles and explicit memories.
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(facts)")}
        for column, default in (("kind", "fact"), ("source", "explicit")):
            if column not in columns:
                self.db.execute(f"ALTER TABLE facts ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
        if "auto_memory" not in {r[1] for r in self.db.execute("PRAGMA table_info(people)")}:
            self.db.execute("ALTER TABLE people ADD COLUMN auto_memory INTEGER NOT NULL DEFAULT 0")
        self.db.commit()

    def close(self):
        self.db.close()

    def setting(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def save_setting(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(value)))

    def people(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT p.*, EXISTS(SELECT 1 FROM faces f WHERE f.person_id=p.id) AS enrolled FROM people p ORDER BY name")]

    def person(self, person_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()
            if row is None:
                raise KeyError("Profile not found")
            return dict(row)

    def create(self, name):
        name = name.strip()
        if not name or len(name) > 60:
            raise ValueError("Use a name between 1 and 60 characters")
        with self.lock, self.db:
            ident = str(uuid.uuid4())
            self.db.execute("INSERT INTO people(id,name,created) VALUES(?,?,?)", (ident, name, now()))
            return self.person(ident)

    def delete(self, ident):
        with self.lock, self.db:
            self.person(ident)
            self.db.execute("DELETE FROM people WHERE id=?", (ident,))

    def facts(self, ident):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM facts WHERE person_id=? ORDER BY created DESC LIMIT 50", (ident,))]

    def remember(self, ident, text):
        text = text.strip()
        if not text or len(text) > 500:
            raise ValueError("Memories must be between 1 and 500 characters")
        with self.lock, self.db:
            self.person(ident)
            if self.db.execute("SELECT COUNT(*) FROM facts WHERE person_id=?", (ident,)).fetchone()[0] >= 50:
                raise ValueError("Memory is full; remove an old fact first")
            item = {"id": str(uuid.uuid4()), "person_id": ident, "text": text, "created": now()}
            self.db.execute("INSERT INTO facts(id,person_id,text,created) VALUES(:id,:person_id,:text,:created)", item)
            return item

    def forget(self, ident, fact_id):
        with self.lock, self.db:
            removed = self.db.execute("DELETE FROM facts WHERE id=? AND person_id=?", (fact_id, ident)).rowcount
            if removed:
                # Summaries may paraphrase the forgotten fact. Remove those too.
                self.db.execute("DELETE FROM episodes WHERE person_id=?", (ident,))
            self.db.execute("DELETE FROM episodes WHERE id=? AND person_id=?", (fact_id, ident))

    def automatic(self, ident, enabled):
        with self.lock, self.db:
            self.person(ident)
            self.db.execute("UPDATE people SET auto_memory=? WHERE id=?", (int(enabled), ident))

    def archive(self, ident):
        with self.lock:
            episodes = [dict(r, kind="conversation", source="automatic") for r in self.db.execute(
                "SELECT * FROM episodes WHERE person_id=? ORDER BY created DESC LIMIT 30", (ident,))]
            return self.facts(ident) + episodes

    def summary(self, ident, session_id):
        with self.lock:
            row = self.db.execute("SELECT text FROM episodes WHERE id=? AND person_id=?",
                                  (ident + ":" + session_id, ident)).fetchone()
            return row[0] if row else ""

    def retrieve(self, ident, query):
        """Bounded, local lexical retrieval; no embedding service or per-query fee."""
        stop = {"the", "and", "that", "with", "what", "have", "you", "your", "about", "this", "remember"}
        words = set(re.findall(r"[\w]+", query.lower())) - stop
        items = self.archive(ident)
        def score(item):
            overlap = words & (set(re.findall(r"[\w]+", item["text"].lower())) - stop)
            return (len(overlap), item["created"])
        facts = sorted((i for i in items if i["kind"] != "conversation"), key=score, reverse=True)[:8]
        episodes = sorted((i for i in items if i["kind"] == "conversation"), key=score, reverse=True)[:2]
        return facts + episodes

    def edit(self, ident, item_id, text):
        text = text.strip()
        if not 1 <= len(text) <= 500:
            raise ValueError("Memories must be between 1 and 500 characters")
        with self.lock, self.db:
            changed = self.db.execute("UPDATE facts SET text=?,source='explicit',created=? WHERE id=? AND person_id=?",
                                      (text, now(), item_id, ident)).rowcount
            if changed:
                self.db.execute("DELETE FROM episodes WHERE person_id=?", (ident,))
            if not changed:
                changed = self.db.execute("SELECT 1 FROM episodes WHERE id=? AND person_id=?", (item_id, ident)).fetchone()
                if changed:
                    # Pin a corrected summary as a manual fact so automatic updates
                    # cannot overwrite the person's correction later in the session.
                    self.remember(ident, text)
                    self.db.execute("DELETE FROM episodes WHERE person_id=?", (ident,))
            if not changed:
                raise KeyError("Memory not found")

    def erase(self, ident):
        with self.lock, self.db:
            self.person(ident)
            self.db.execute("DELETE FROM facts WHERE person_id=?", (ident,))
            self.db.execute("DELETE FROM episodes WHERE person_id=?", (ident,))
            self.db.execute("UPDATE people SET turns=0,last_seen=NULL,auto_memory=0 WHERE id=?", (ident,))

    def absorb(self, ident, session_id, payload):
        """Apply bounded model notes only to the confirmed, opted-in owner.

        Model corrections may replace automatic notes, never manual edits. Invalid
        proposals are ignored and cannot select another person's memory.
        """
        with self.lock, self.db:
            if not self.person(ident)["auto_memory"] or not isinstance(payload, dict):
                return
            updates = payload.get("updates", [])
            for item in updates[:3] if isinstance(updates, list) else []:
                if not isinstance(item, dict):
                    continue
                text, kind = item.get("text"), item.get("kind")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 500 or not isinstance(kind, str) or kind not in {"fact", "preference", "project"}:
                    continue
                text = text.strip()
                replace = item.get("replace_id")
                if replace:
                    if not isinstance(replace, str):
                        continue
                    self.db.execute("UPDATE facts SET text=?,kind=?,created=? WHERE id=? AND person_id=? AND source='automatic'",
                                    (text, kind, now(), replace, ident))
                elif not self.db.execute("SELECT 1 FROM facts WHERE person_id=? AND lower(text)=lower(?)", (ident, text)).fetchone():
                    if len(self.facts(ident)) < 50:
                        self.db.execute("INSERT INTO facts(id,person_id,text,created,kind,source) VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), ident, text, now(), kind, "automatic"))
            summary = payload.get("summary")
            if isinstance(summary, str) and 1 <= len(summary.strip()) <= 500:
                # Owner is part of the key even when callers reuse a session ID.
                key = ident + ":" + session_id
                self.db.execute("INSERT OR REPLACE INTO episodes VALUES(?,?,?,?)", (key, ident, summary.strip(), now()))
                self.db.execute("DELETE FROM episodes WHERE person_id=? AND id NOT IN (SELECT id FROM episodes WHERE person_id=? ORDER BY created DESC LIMIT 30)", (ident, ident))

    def interacted(self, ident):
        with self.lock, self.db:
            self.db.execute("UPDATE people SET turns=turns+1,last_seen=? WHERE id=?", (now(), ident))

    def enroll(self, ident, embedding):
        with self.lock, self.db:
            self.person(ident)
            self.db.execute("INSERT OR REPLACE INTO faces VALUES(?,?)", (ident, json.dumps(embedding)))

    def embeddings(self):
        with self.lock:
            return [(r[0], json.loads(r[1])) for r in self.db.execute("SELECT person_id,embedding FROM faces")]

    def forget_face(self, ident):
        with self.lock, self.db:
            self.db.execute("DELETE FROM faces WHERE person_id=?", (ident,))
