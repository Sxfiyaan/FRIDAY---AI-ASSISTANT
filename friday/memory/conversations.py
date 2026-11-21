"""Key-scoped, encrypted conversation history in the local application database."""

import hashlib
import hmac
import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from uuid import UUID

from cryptography.fernet import Fernet

from friday.config import HistorySettings
from friday.llm.base import Message
from friday.safety.privacy import SafeError


class Conversations:
    """Possession of an independent high-entropy history key identifies a local user."""

    def __init__(self, settings: HistorySettings) -> None:
        self.settings = settings
        key = os.environ.get(settings.key_env, "").encode()
        if settings.path is None:
            raise SafeError("configuration")
        try:
            self.cipher = Fernet(key)
        except (ValueError, TypeError):
            raise SafeError("configuration") from None
        self.path = settings.path
        self.owner = hmac.digest(key, b"friday-history-owner-v1", hashlib.sha256).hex()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # SQLite uses the existing file's permissions for its rollback journal.
        self.path.touch(mode=0o600, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("""CREATE TABLE IF NOT EXISTS turns (
                    owner TEXT NOT NULL, conversation TEXT NOT NULL, created INTEGER NOT NULL,
                    expires INTEGER NOT NULL, ciphertext BLOB NOT NULL)""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS conversation_owner ON turns(owner, conversation)"
            )
            now = int(time.time())
            db.execute(
                "DELETE FROM turns WHERE expires <= ? OR (owner=? AND created <= ?)",
                (now, self.owner, now - self.settings.retention_days * 86400),
            )
            yield db

    def append(self, conversation: UUID, prompt: str, answer: str) -> None:
        if not self.settings.enabled:
            return
        payload = json.dumps([str(conversation), prompt, answer]).encode()
        now = int(time.time())
        with self.connection() as db:
            db.execute(
                "INSERT INTO turns VALUES (?, ?, ?, ?, ?)",
                (
                    self.owner,
                    str(conversation),
                    now,
                    now + self.settings.retention_days * 86400,
                    self.cipher.encrypt(payload),
                ),
            )

    def list_ids(self) -> list[UUID]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT conversation FROM turns WHERE owner=? "
                "GROUP BY conversation ORDER BY MAX(rowid) DESC",
                (self.owner,),
            )
            return [UUID(row[0]) for row in rows]

    def read(self, conversation: UUID) -> list[Message]:
        messages: list[Message] = []
        with self.connection() as db:
            rows = db.execute(
                "SELECT ciphertext FROM turns WHERE owner=? AND conversation=? ORDER BY rowid",
                (self.owner, str(conversation)),
            )
            for (ciphertext,) in rows:
                identifier, prompt, answer = json.loads(self.cipher.decrypt(ciphertext))
                if identifier != str(conversation):
                    raise SafeError("storage")
                messages.extend(
                    [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}]
                )
        return messages

    def delete(self, conversation: UUID) -> bool:
        with self.connection() as db:
            return (
                db.execute(
                    "DELETE FROM turns WHERE owner=? AND conversation=?",
                    (self.owner, str(conversation)),
                ).rowcount
                > 0
            )
