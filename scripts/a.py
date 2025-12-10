#!/usr/bin/env python3
"""
Simple token manager.
Stores a single API token in a local sqlite DB (outside the repo) and supports:
  --rotate    Generate and store a new token, print it to stdout.
  --show      Print the current token to stdout.
  --validate TOKEN   Exit 0 if matches current token, else 1.

Note: Keep file permissions on the DB path restricted (root-only) to avoid leakage.
"""

import argparse
import os
import sqlite3
import sys
import time
import secrets
from pathlib import Path

# Default location outside the repo; adjust if desired.
DB_PATH = Path("/var/lib/mvospette/secret.db")


def ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # If sqlite file exists, leave perms as-is; otherwise create with restrictive perms.
    if not DB_PATH.exists():
        # Create the file with 0o600
        fd = os.open(DB_PATH, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS token (id INTEGER PRIMARY KEY CHECK (id=1), value TEXT NOT NULL, created_at INTEGER NOT NULL)"
    )
    conn.commit()
    return conn


def get_token(conn):
    cur = conn.execute("SELECT value FROM token WHERE id=1")
    row = cur.fetchone()
    return row[0] if row else None


def set_token(conn, value):
    now = int(time.time())
    conn.execute(
        "INSERT INTO token (id, value, created_at) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET value=excluded.value, created_at=excluded.created_at",
        (value, now),
    )
    conn.commit()


def rotate(conn):
    token = secrets.token_urlsafe(32)
    set_token(conn, token)
    return token


def main():
    parser = argparse.ArgumentParser(description="Token manager")
    parser.add_argument("--rotate", action="store_true", help="Generate and store a new token, print it")
    parser.add_argument("--show", action="store_true", help="Print the current token")
    parser.add_argument("--validate", metavar="TOKEN", help="Validate TOKEN against stored value")
    args = parser.parse_args()

    if not (args.rotate or args.show or args.validate):
        parser.print_help()
        return 1

    conn = ensure_db()
    try:
        if args.rotate:
            token = rotate(conn)
            print(token)
            return 0
        if args.show:
            token = get_token(conn)
            if token is None:
                print("No token set", file=sys.stderr)
                return 1
            print(token)
            return 0
        if args.validate is not None:
            stored = get_token(conn)
            if stored is None:
                return 1
            return 0 if secrets.compare_digest(stored, args.validate) else 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
