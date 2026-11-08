"""Append-only activity accounting; constructed before model/environment use."""
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import json
import time


class Ledger:
    def __init__(self, path, phase):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.phase = phase
        self.counts = Counter()
        self.sequence = 0
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                row = json.loads(line)
                self.counts.update(row['delta'])
                self.sequence = row['sequence']
        self.pending = Counter()

    def add(self, name, count=1):
        self.counts[name] += count
        self.pending[name] += count

    def flush(self, operation, **details):
        self.sequence += 1
        row = dict(sequence=self.sequence, wall_ns=time.time_ns(), phase=self.phase,
                   operation=operation, delta=dict(self.pending), details=details)
        with self.path.open('a') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
        self.pending.clear()

    @contextmanager
    def call(self, name, **details):
        self.add(name)
        try:
            yield
        except Exception as error:
            self.flush(name, error=f'{type(error).__name__}: {error}', **details)
            raise
        else:
            self.flush(name, **details)
