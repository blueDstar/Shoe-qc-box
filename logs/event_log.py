from __future__ import annotations

from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
import csv
import json


class EventLog:
    def __init__(self, path=None):
        self.events = deque(maxlen=10000)
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, time_s, kind, message, **data):
        row = {"timestamp":datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="milliseconds"),
               "simulation_s":round(time_s,6),"kind":kind,"message":message,**data}
        self.events.append(row)
        if self.path:
            with self.path.open("a",encoding="utf-8") as f:
                f.write(json.dumps(row,ensure_ascii=False)+"\n")

    def export_json(self, path):
        Path(path).write_text(json.dumps(list(self.events),indent=2,ensure_ascii=False),encoding="utf-8")

    def export_csv(self,path):
        with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["timestamp","simulation_s","kind","message","data"])
            w.writeheader()
            for row in self.events:
                w.writerow({**{k:row[k] for k in ("timestamp","simulation_s","kind","message")},
                            "data":json.dumps({k:v for k,v in row.items() if k not in ("timestamp","simulation_s","kind","message")})})
