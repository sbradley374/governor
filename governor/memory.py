"""Local, explicit memory. No raw recordings or camera frames are persisted."""
import json
import os
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
        """)
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
            self.db.execute("INSERT INTO facts VALUES(:id,:person_id,:text,:created)", item)
            return item

    def forget(self, ident, fact_id):
        with self.lock, self.db:
            self.db.execute("DELETE FROM facts WHERE id=? AND person_id=?", (fact_id, ident))

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
