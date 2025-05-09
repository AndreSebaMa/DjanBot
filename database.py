import sqlite3
import time
from typing import List, Tuple, Optional

DB_PATH = 'worklog.db'

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('''
      CREATE TABLE IF NOT EXISTS work_sessions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      TEXT    NOT NULL,
        start_ts     INTEGER NOT NULL,
        stop_ts      INTEGER,
        note         TEXT
      )
    ''')
    db.commit()
    db.close()

def start_session(user_id: str, note: str) -> None:
    db = sqlite3.connect(DB_PATH)
    db.execute('''
      INSERT INTO work_sessions (user_id, start_ts, note)
      VALUES (?, ?, ?)
    ''', (user_id, int(time.time()), note))
    db.commit()
    db.close()

def stop_session(user_id: str, finish_note: Optional[str] = "") -> float:
    """
    Stops the active session for user_id, optionally appends finish_note,
    and returns hours worked.
    """
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
      SELECT id, start_ts, note
      FROM work_sessions
      WHERE user_id=? AND stop_ts IS NULL
      ORDER BY start_ts DESC
      LIMIT 1
    ''', (user_id,))
    row = cur.fetchone()
    if not row:
        db.close()
        raise ValueError("No active session")

    sess_id, start_ts, orig_note = row
    stop_ts = int(time.time())

    # build new note by appending finish_note if provided
    new_note = orig_note
    if finish_note:
        new_note = f"{orig_note} [Finished: {finish_note}]"

    db.execute('''
      UPDATE work_sessions
      SET stop_ts=?, note=?
      WHERE id=?
    ''', (stop_ts, new_note, sess_id))
    db.commit()
    db.close()

    return (stop_ts - start_ts) / 3600

def auto_stop_overdue(max_hours: int = 16) -> List[Tuple[str, float, int]]:
    cutoff = int(time.time()) - max_hours * 3600
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
      SELECT id, user_id, start_ts, note
      FROM work_sessions
      WHERE stop_ts IS NULL AND start_ts <= ?
    ''', (cutoff,))
    overdue = cur.fetchall()

    results = []
    for sess_id, user_id, start_ts, note in overdue:
        stop_ts = start_ts + max_hours * 3600
        db.execute('''
          UPDATE work_sessions
          SET stop_ts=?
          WHERE id=?
        ''', (stop_ts, sess_id))
        hours = (stop_ts - start_ts) / 3600
        results.append((user_id, hours, sess_id))

    db.commit()
    db.close()
    return results

def get_history(user_id: str, limit: int = 10) -> List[Tuple[int, int, int, float, str]]:
    """
    Returns up to `limit` past sessions:
      (session_id, start_ts, stop_ts, hours, note)
      newest first.
    """
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
      SELECT
        id,
        start_ts,
        stop_ts,
        (stop_ts - start_ts)/3600.0 AS hours,
        note
      FROM work_sessions
      WHERE user_id=? AND stop_ts IS NOT NULL
      ORDER BY start_ts DESC
      LIMIT ?
    ''', (user_id, limit))
    rows = cur.fetchall()
    db.close()
    return rows

def get_summary(user_id: str, days: int = 7) -> float:
    since = int(time.time()) - days * 86400
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
      SELECT SUM(stop_ts - start_ts)/3600.0
      FROM work_sessions
      WHERE user_id=? AND stop_ts IS NOT NULL AND start_ts >= ?
    ''', (user_id, since))
    total = cur.fetchone()[0] or 0.0
    db.close()
    return total
