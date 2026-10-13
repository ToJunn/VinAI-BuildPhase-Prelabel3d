import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f'.{uuid.uuid4().hex}.tmp')
    temp.write_text(json.dumps(data, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def runtime_size(root):
    size = 0
    for path in root.rglob('*'):
        try:
            if path.is_file():
                size += path.stat().st_size
        except FileNotFoundError:
            # Atomic worker writes may replace/remove a temporary file while scanning.
            continue
    return size


class Store:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.file = root / 'app.db'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT, data TEXT)')

    def connect(self):
        return sqlite3.connect(self.file, timeout=30)

    def put(self, record, kind='job'):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO records VALUES (?, ?, ?)',
                       (record['id'], kind, json.dumps(record)))
        return record

    def get(self, id, kind='job'):
        with self.connect() as db:
            row = db.execute('SELECT data FROM records WHERE id=? AND kind=?', (id, kind)).fetchone()
        if not row:
            raise KeyError(id)
        return json.loads(row[0])

    def list(self, kind='job'):
        with self.connect() as db:
            rows = db.execute('SELECT data FROM records WHERE kind=? ORDER BY rowid DESC', (kind,)).fetchall()
        return [json.loads(r[0]) for r in rows]


def new_record(request, parent=None):
    return {'id': uuid.uuid4().hex, 'request': request, 'status': 'queued', 'processed': 0,
            'total': len(request['sample_tokens']), 'current_sample': None, 'elapsed': 0,
            'message': 'Waiting', 'error': None, 'parent_job_id': parent,
            'created_at': datetime.now(timezone.utc).isoformat()}
