"""Host-side sampler: exports only memory, never credentials or Docker access."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def docker(*arguments):
    return subprocess.check_output(["docker", *arguments], text=True, timeout=15).strip()


def sample(prefix, suffix="", active_slot="legacy"):
    result = {}
    for component in ("rails", "sidekiq", "postgres", "redis"):
        name = f"{prefix}-{component}{suffix}"
        if component in ("rails", "sidekiq") and active_slot in ("blue", "green"):
            name = f"devops-grupo7-{active_slot}-{component}-1"
        try:
            # cgroup v2 reports exact bytes. Working set follows Docker's cache subtraction.
            values = docker("exec", name, "cat", "/sys/fs/cgroup/memory.current",
                            "/sys/fs/cgroup/memory.stat").splitlines()
            current = int(values[0])
            stats = dict(line.split() for line in values[1:])
            inactive = int(stats["inactive_file"])
            used = current - inactive if inactive < current else current
            limit = int(docker("inspect", "--format", "{{.HostConfig.Memory}}", name))
            result[component] = {"working_set_bytes": used, "limit_bytes": limit,
                                 "timestamp": time.time()}
        except (subprocess.SubprocessError, ValueError, KeyError):
            # Missing/stopped containers do not inherit old values.
            print(f"No current memory sample for {component}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="devops-grupo7-e2")
    parser.add_argument("--suffix", default="", help="Compose suffix, e.g. -1; empty preserves local names")
    parser.add_argument("--directory", type=Path, help="Output directory; defaults to local .runtime")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--deployment-state", type=Path, help="Estado opcional del CD GCP")
    args = parser.parse_args()
    directory = args.directory or Path(__file__).resolve().parents[1] / ".runtime"
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        started = time.monotonic()
        slot = "legacy"
        if args.deployment_state and args.deployment_state.exists():
            slot = json.loads(args.deployment_state.read_text())["active"]["slot"]
        result = sample(args.prefix, args.suffix, slot)
        temporary = directory / "resources.tmp"
        temporary.write_text(json.dumps(result), encoding="utf-8")
        os.replace(temporary, directory / "resources.json")
        print(f"Memory snapshot: {len(result)}/4 components", flush=True)
        if args.once:
            break
        time.sleep(max(0, 15 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
