"""Serves host-collected memory without mounting a Docker socket."""
import json
from pathlib import Path
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def exposition(snapshot, now):
    lines = [
        "# TYPE unal_container_memory_working_set_bytes gauge",
        "# TYPE unal_container_memory_limit_bytes gauge",
        "# TYPE unal_container_memory_sample_timestamp_seconds gauge",
        "# TYPE unal_container_memory_collection_success gauge",
    ]
    for component in ("rails", "sidekiq", "postgres", "redis"):
        labels = f'project="devops-grupo7",environment="lab",component="{component}"'
        value = snapshot.get(component)
        fresh = value is not None and 0 <= now - value["timestamp"] <= 45
        lines.append(f"unal_container_memory_collection_success{{{labels}}} {int(fresh)}")
        if not fresh:
            continue
        lines.append(f'unal_container_memory_working_set_bytes{{{labels}}} {value["working_set_bytes"]}')
        lines.append(f'unal_container_memory_sample_timestamp_seconds{{{labels}}} {value["timestamp"]}')
        if value["limit_bytes"] > 0:
            lines.append(f'unal_container_memory_limit_bytes{{{labels}}} {value["limit_bytes"]}')
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        try:
            snapshot = json.loads(Path("/data/resources.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            snapshot = {}
        body = exposition(snapshot, time.time()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9100), Handler).serve_forever()
