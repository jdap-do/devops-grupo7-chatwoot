"""Persist local Alertmanager notifications from the integrated laboratory."""

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

JOURNAL = Path('/data/notifications.jsonl')
EVENTS = [json.loads(line) for line in JOURNAL.read_text().splitlines()] if JOURNAL.exists() else []
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/healthz':
            self.reply({'source': 'chatwoot-lab', 'status': 'ok'})
        elif parsed.path == '/notifications':
            try:
                since_id = int(parse_qs(parsed.query).get('since_id', ['0'])[0])
            except ValueError:
                self.send_error(422)
                return
            with LOCK:
                self.reply({'source': 'chatwoot-lab', 'events': [e for e in EVENTS if e['id'] > since_id]})
        else:
            self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != '/alerts':
            self.send_error(404)
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            if payload['status'] not in ('firing', 'resolved') or not isinstance(payload['alerts'], list):
                raise ValueError('Invalid webhook')
        except (ValueError, KeyError, TypeError):
            self.send_error(422)
            return
        with LOCK:
            event = {'id': len(EVENTS) + 1, 'received_at': datetime.now(timezone.utc).isoformat(), 'payload': payload}
            with JOURNAL.open('a') as journal:
                journal.write(json.dumps(event) + '\n')
            EVENTS.append(event)
        self.reply({'accepted': True})

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
