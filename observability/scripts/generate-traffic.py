"""Bounded sequential HTTP traffic for the Chatwoot laboratory."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:3011")
    parser.add_argument("--client-file", type=Path,
                        default=Path(__file__).resolve().parents[1] / ".runtime/chatwoot-client.json")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--interval", type=float, default=1)
    args = parser.parse_args()
    if not 1 <= args.duration <= 1800 or args.interval < 1:
        parser.error("Use duration 1..1800 seconds and interval >= 1 second")
    client = json.loads(args.client_file.read_text(encoding="utf-8"))
    prefix = f'/api/v1/accounts/{int(client["account_id"])}'
    paths = [prefix + '/conversations', prefix + '/conversations/search?q=hola',
             prefix + f'/conversations/{int(client["conversation_id"])}/messages', prefix + '/contacts']
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    results = Counter()
    durations = []
    try:
        while time.monotonic() - started < args.duration:
            request_started = time.monotonic()
            try:
                path = paths[len(durations) % len(paths)]
                request = Request(args.url.rstrip('/') + path, headers={"api_access_token": client["token"]})
                with urlopen(request, timeout=7) as response:
                    body = response.read()
                    if response.status == 200:
                        json.loads(body)  # A login HTML page must not pass as a successful API read.
                    status = str(response.status)
            except HTTPError as error:
                status = str(error.code)
                error.close()
            except (URLError, TimeoutError, OSError):
                status = "connection_error"
            except ValueError:
                status = "invalid_json_response"
            durations.append(time.monotonic() - request_started)
            results[status] += 1
            remaining = args.duration - (time.monotonic() - started)
            time.sleep(max(0, min(remaining, args.interval - durations[-1])))
    finally:
        summary = {"started_at_utc": started_at,
                   "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                   "elapsed_seconds": round(time.monotonic() - started, 3),
                   "planned_interval_seconds": args.interval,
                   "requests": sum(results.values()), "statuses": dict(results),
                   "mean_client_duration_seconds": sum(durations) / len(durations) if durations else None}
        directory = Path(__file__).resolve().parents[1] / ".runtime"
        directory.mkdir(exist_ok=True)
        path = directory / ("traffic-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)
        print("Local result:", path, flush=True)


if __name__ == "__main__":
    main()
