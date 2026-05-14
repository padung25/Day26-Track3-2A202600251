from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

try:
    from .db import default_db_path
except ImportError:  # pragma: no cover - direct script execution
    from db import default_db_path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    cohort TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'dropped')),
    enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, course_id)
);
"""


SEED_SQL = """
INSERT INTO students (name, email, cohort, created_at) VALUES
    ('An Nguyen', 'an.nguyen@example.com', 'A1', '2026-01-08T09:00:00'),
    ('Bao Tran', 'bao.tran@example.com', 'A1', '2026-01-09T09:00:00'),
    ('Chi Pham', 'chi.pham@example.com', 'A2', '2026-01-10T09:00:00'),
    ('Dung Le', 'dung.le@example.com', 'B1', '2026-01-11T09:00:00'),
    ('Ena Vo', 'ena.vo@example.com', 'A1', '2026-01-12T09:00:00');

INSERT INTO courses (code, title, credits) VALUES
    ('MCP101', 'MCP Foundations', 3),
    ('SQL201', 'Practical SQL', 4),
    ('AI301', 'AI Product Integration', 3);

INSERT INTO enrollments (student_id, course_id, score, status, enrolled_at) VALUES
    (1, 1, 91.5, 'completed', '2026-02-01T09:00:00'),
    (1, 2, 87.0, 'active', '2026-02-03T09:00:00'),
    (2, 1, 78.0, 'completed', '2026-02-01T09:00:00'),
    (2, 3, 82.5, 'active', '2026-02-05T09:00:00'),
    (3, 2, 94.0, 'completed', '2026-02-03T09:00:00'),
    (4, 1, 68.0, 'dropped', '2026-02-01T09:00:00'),
    (5, 1, 88.5, 'completed', '2026-02-01T09:00:00'),
    (5, 3, 92.0, 'active', '2026-02-05T09:00:00');
"""


def create_database(db_path: str | Path | None = None, reset: bool = False) -> Path:
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()

    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_SQL)
        if reset or is_empty(connection):
            connection.executescript(SEED_SQL)
        connection.commit()
    return path


def is_empty(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT COUNT(*) FROM students").fetchone()
    return bool(row and row[0] == 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the SQLite database for the MCP lab.")
    parser.add_argument("--db-path", type=Path, default=default_db_path())
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the database.")
    args = parser.parse_args()

    path = create_database(args.db_path, reset=args.reset)
    print(f"Database ready: {path}")


if __name__ == "__main__":
    main()
