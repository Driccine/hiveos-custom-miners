"""Read the latest periodic report from Crypto Connection Miner 0.10.1."""
import json
import re
import sys
import time
from pathlib import Path


def main():
    log_base = sys.argv[1]
    now = time.time()
    try:
        started = int(Path(log_base + ".started").read_text())
        with open(log_base + ".log", "rb") as log:
            length = log.seek(0, 2)
            log.seek(max(0, length - 32768))
            lines = log.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return

    for line in reversed(lines):
        match = re.search(
            r"\[([^]]+)\] (\d+\.\d+) MH/s \(([^)]*)\) \| shares sent \d+, "
            r"accepted (\d+), rejected (\d+),",
            line,
        )
        if match:
            break
    else:
        return

    timestamp, total, devices, accepted, rejected = match.groups()
    try:
        reported_at = time.mktime(time.strptime(timestamp, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return
    if now - reported_at > 45 or reported_at < started:
        return

    rates = {
        int(index): float(rate)
        for index, rate in re.findall(r"GPU(\d+) (\d+\.\d+)", devices)
    }
    stats = {
        "hs": [rates[index] for index in sorted(rates)],
        "hs_units": "mhs",
        "uptime": max(0, int(now - started)),
        "ver": "0.10.1",
        "ar": [int(accepted), int(rejected)],
        "algo": "ting",
    }
    print(f"{float(total) * 1000:.2f}", json.dumps(stats, separators=(",", ":")))


if __name__ == "__main__":
    main()
