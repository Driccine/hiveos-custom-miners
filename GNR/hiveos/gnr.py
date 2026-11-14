#!/usr/bin/env python3
"""HiveOS adapter for the unmodified Genoryn Krypton miner (Python 3.8+).
No wallet secrets, shell evaluation, package installation or CPU mining.
"""
import argparse
import csv
import ctypes
import hashlib
import io
import json
import math
import os
import platform
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

VERSION = "1.1.0"
UPSTREAM = "1.0.37"
DEFAULT_NODE = "https://genoryn.io"
STATUS_TTL = 45
ROOT = Path(__file__).resolve().parent


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(str(tmp), "w", encoding="utf-8") as handle:
        os.chmod(str(tmp), 0o600)
        json.dump(value, handle, allow_nan=False)
        handle.write("\n")
    os.replace(str(tmp), str(path))


def config_from_env(env):
    address = env.get("GNR_WALLET", "").strip()
    if address.startswith("gnrs1"):
        raise ValueError("Utiliser l'adresse PUBLIQUE COMPLETE gnr1..., pas l'adresse courte gnrs1...; ne pas ajouter .worker.")
    if not re.fullmatch(r"gnr1[0-9a-z]{100,8192}", address):
        raise ValueError("Wallet invalide: coller l'adresse publique complete gnr1... dans le wallet GNR HiveOS. Template: %WAL% uniquement.")
    node = env.get("GNR_NODE", "").strip() or DEFAULT_NODE
    from urllib.parse import urlsplit
    parsed = urlsplit(node)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            re.search(r"\s", node)):
        raise ValueError("Pool URL: une seule URL de noeud HTTP(S), sans identifiants, ni Stratum.")
    parser = argparse.ArgumentParser(prog="Extra config", allow_abbrev=False)
    parser.add_argument("--devices", default="")
    parser.add_argument("--batch", type=int)
    args = parser.parse_args(shlex.split(env.get("GNR_EXTRA", "")))
    devices = None
    if args.devices:
        if not re.fullmatch(r"\d+(,\d+)*", args.devices):
            raise ValueError("--devices attend des indices separes par des virgules, par exemple 0,1.")
        devices = [int(x) for x in args.devices.split(",")]
        if len(devices) != len(set(devices)):
            raise ValueError("Un GPU ne peut pas etre selectionne deux fois.")
    if args.batch is not None and not (256 <= args.batch <= 4294967295):
        raise ValueError("--batch doit etre compris entre 256 et 4294967295.")
    return {"schema": 1, "node": node.rstrip("/"), "address": address,
            "devices": devices, "batch": args.batch}


def command(binary, cfg, address_file, device):
    cmd = [str(binary), "--node", cfg["node"], "--address-file", str(address_file),
           "--backend", "cuda", "--devices", str(device), "--json"]
    if cfg.get("batch") is not None:
        cmd += ["--batch", str(cfg["batch"])]
    return cmd


def select_devices(probe, requested):
    gpus = {int(g["index"]): g for g in probe.get("gpus", []) if g.get("backend") == "cuda"}
    selected = sorted(gpus) if requested is None else requested
    if not selected:
        raise RuntimeError("Aucun GPU CUDA. " + "; ".join(probe.get("notes", [])))
    for i in selected:
        if i not in gpus or not gpus[i].get("usable", False):
            reason = gpus.get(i, {}).get("error", "GPU non detecte")
            raise RuntimeError("GPU %s inutilisable: %s. Aucun repli CPU." % (i, reason))
    return selected


def cuda_buses():
    """Map actual CUDA ordinals to PCI IDs; do not guess NVML/index ordering."""
    try:
        lib = ctypes.CDLL("libcuda.so.1")
        if lib.cuInit(0) != 0:
            return {}
        count = ctypes.c_int()
        if lib.cuDeviceGetCount(ctypes.byref(count)) != 0:
            return {}
        result = {}
        for ordinal in range(count.value):
            device = ctypes.c_int()
            bus = ctypes.create_string_buffer(64)
            if lib.cuDeviceGet(ctypes.byref(device), ordinal) == 0 and lib.cuDeviceGetPCIBusId(bus, 64, device) == 0:
                result[ordinal] = bus.value.decode("ascii").lower()[-12:]
        return result
    except (OSError, AttributeError):
        return {}


def telemetry():
    try:
        output = subprocess.check_output([
            "nvidia-smi", "--query-gpu=pci.bus_id,temperature.gpu,fan.speed",
            "--format=csv,noheader,nounits"], timeout=5, universal_newlines=True, stderr=subprocess.DEVNULL)
        result = {}
        for row in csv.reader(io.StringIO(output)):
            if len(row) != 3:
                continue
            def integer(value):
                value = value.strip()
                return int(value) if value.isdigit() else None
            result[row[0].strip().lower()[-12:]] = (integer(row[1]), integer(row[2]))
        return result
    except (OSError, subprocess.SubprocessError):
        return {}


def accepted_status(line):
    try:
        obj = json.loads(line)
        if obj.get("event") != "status":
            return None
        rate = float(obj["hashrate_hs"])
        if not math.isfinite(rate) or rate < 0:
            return None
        for key in ("accepted_shares", "rejected", "accepted_blocks"):
            if isinstance(obj.get(key, 0), bool) or int(obj.get(key, 0)) < 0:
                return None
        return obj
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def snapshot(states, selected, buses, temperatures, started, now):
    rates, accepted, rejected, blocks = [], 0, 0, 0
    for i in selected:
        state = states.get(i, {})
        obj = state.get("data", {})
        fresh = now - state.get("seen", 0) <= STATUS_TTL
        rates.append(float(obj.get("hashrate_hs", 0)) if fresh else 0.0)
        # accepted_shares already INCLUDES shares that were full blocks.
        accepted += int(obj.get("accepted_shares", 0))
        rejected += int(obj.get("rejected", 0))
        blocks += int(obj.get("accepted_blocks", 0))
    stats = {"hs": rates, "hs_units": "hs", "uptime": max(0, int(now - started)),
             "ar": [accepted, rejected], "algo": "kryptohash", "ver": UPSTREAM}
    if all(i in buses for i in selected):
        stats["bus_numbers"] = [int(buses[i].split(":")[-2], 16) for i in selected]
        temps = [temperatures.get(buses[i], (None, None))[0] for i in selected]
        fans = [temperatures.get(buses[i], (None, None))[1] for i in selected]
        if all(v is not None for v in temps):
            stats["temp"] = temps
        if all(v is not None for v in fans):
            stats["fan"] = fans
    return {"updated": now, "khs": sum(rates) / 1000.0, "stats": stats,
            "accepted_blocks": blocks, "devices": selected}


def read_stats(path, now=None):
    now = time.time() if now is None else now
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not 0 <= now - float(value["updated"]) <= STATUS_TTL:
            raise ValueError("stale")
        return float(value["khs"]), value["stats"]
    except (OSError, ValueError, KeyError, TypeError):
        return 0.0, None


def check_binary(binary):
    if platform.machine() not in ("x86_64", "amd64"):
        raise RuntimeError("Paquet x86-64 uniquement.")
    libc, version = platform.libc_ver()
    if libc == "glibc" and tuple(int(x) for x in version.split(".")[:2]) < (2, 31):
        raise RuntimeError("glibc >= 2.31 requise: image HiveOS Ubuntu 20.04+; aucune mise a jour automatique du systeme.")
    if not binary.is_file():
        raise RuntimeError("Binaire absent: installer l'archive de RELEASE, pas le ZIP du code source.")
    done = subprocess.run([str(binary), "--version"], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True, timeout=15)
    if done.returncode != 0:
        raise RuntimeError("Binaire incompatible: " + done.stdout.strip())
    print(done.stdout.strip(), flush=True)


def check_node(url):
    req = urllib.request.Request(url + "/v1/info", headers={"User-Agent": "gnr-hiveos/" + VERSION})
    with urllib.request.urlopen(req, timeout=20) as response:
        info = json.load(response)
    if not isinstance(info, dict):
        raise RuntimeError("Reponse du noeud invalide.")
    # Older APIs may omit these fields. Never accept an explicitly different network.
    if info.get("network", "mainnet") != "mainnet":
        raise RuntimeError("Le noeud n'est pas sur mainnet.")
    if "chain_id" in info and info["chain_id"] != "genoryn-krypton-mainnet-1":
        raise RuntimeError("Identifiant de chaine inattendu.")
    return info


def run(config_path):
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    # Revalidate saved config; never pass arbitrary JSON values to the miner.
    extra = []
    if cfg.get("devices") is not None:
        extra += ["--devices", ",".join(str(x) for x in cfg["devices"])]
    if cfg.get("batch") is not None:
        extra += ["--batch", str(cfg["batch"])]
    cfg = config_from_env({"GNR_WALLET": cfg["address"], "GNR_NODE": cfg["node"], "GNR_EXTRA": shlex.join(extra)})
    binary = ROOT / "krypton-miner"
    check_binary(binary)
    info = check_node(cfg["node"])
    print("Noeud %s | hauteur %s | CUDA uniquement" % (cfg["node"], info.get("height", "?")), flush=True)
    probe = subprocess.run([str(binary), "--list-devices", "--json"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
    if probe.returncode:
        raise RuntimeError("Detection CUDA echouee: " + probe.stderr.strip())
    selected = select_devices(json.loads(probe.stdout), cfg["devices"])
    run_dir = Path(config_path).parent
    address_file = run_dir / "address.txt"
    address_file.write_text(cfg["address"] + "\n", encoding="ascii")
    os.chmod(str(address_file), 0o600)
    buses = cuda_buses()
    states = {}
    processes = []
    lock = threading.Lock()
    stop = threading.Event()
    started = time.time()
    stats_file = run_dir / "stats.json"
    print("GPU selectionnes: " + ",".join(map(str, selected)), flush=True)

    def request_stop(signum, frame):
        stop.set()

    def consume(index, proc):
        for line in proc.stdout:
            parsed = accepted_status(line)
            if parsed is not None:
                with lock:
                    states[index] = {"seen": time.time(), "data": parsed}
                print("GPU %s | %.3f MH/s | shares %s | rejets %s | blocs %s" % (
                    index, float(parsed["hashrate_hs"]) / 1e6,
                    parsed.get("accepted_shares", 0), parsed.get("rejected", 0),
                    parsed.get("accepted_blocks", 0)), flush=True)
            else:
                print("GPU %s | %s" % (index, line.rstrip()), flush=True)

    old_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, request_stop)
    try:
        for index in selected:
            # Same process group as HiveOS. SIGTERM is forwarded; no detached daemons.
            proc = subprocess.Popen(command(binary, cfg, address_file, index),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, bufsize=1)
            processes.append((index, proc))
            threading.Thread(target=consume, args=(index, proc), daemon=True).start()
        while not stop.is_set():
            for index, proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError("Mineur GPU %s arrete (code %s); HiveOS peut le relancer." % (index, proc.returncode))
            now = time.time()
            with lock:
                saved = dict(states)
            atomic_json(stats_file, snapshot(saved, selected, buses, telemetry(), started, now))
            for index in selected:
                seen = saved.get(index, {}).get("seen", started)
                if now - seen > 180:
                    raise RuntimeError("GPU %s: aucune statistique depuis 180 s." % index)
            stop.wait(5)
    finally:
        stop.set()
        for _, proc in processes:
            if proc.poll() is None:
                proc.terminate()
        deadline = time.monotonic() + 10
        for _, proc in processes:
            try:
                proc.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        atomic_json(stats_file, {"updated": time.time(), "khs": 0, "stats": None})
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)



def run_multi(config_path):
    """Use one official CUDA miner for all GPUs: one dataset lifecycle / node client."""
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    extra = []
    if cfg.get("devices") is not None:
        extra += ["--devices", ",".join(str(x) for x in cfg["devices"])]
    if cfg.get("batch") is not None:
        extra += ["--batch", str(cfg["batch"])]
    cfg = config_from_env({"GNR_WALLET": cfg["address"],
                           "GNR_NODE": cfg["node"], "GNR_EXTRA": shlex.join(extra)})
    binary = ROOT / "krypton-miner"
    check_binary(binary)
    info = check_node(cfg["node"])
    print("Node %s | height %s | CUDA only" % (cfg["node"], info.get("height", "?")), flush=True)
    probe = subprocess.run([str(binary), "--list-devices", "--json"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
    if probe.returncode:
        raise RuntimeError("CUDA detection failed: " + probe.stderr.strip())
    selected = select_devices(json.loads(probe.stdout), cfg["devices"])
    run_dir = Path(config_path).parent
    address_file = run_dir / "address.txt"
    address_file.write_text(cfg["address"] + "\n", encoding="ascii")
    os.chmod(str(address_file), 0o600)
    stats_file = run_dir / "stats.json"
    started = time.time()
    last_status = started
    latest = None
    stop = threading.Event()
    print("Single official process for %d GPUs: %s" %
          (len(selected), ",".join(map(str, selected))), flush=True)

    def request_stop(signum, frame):
        stop.set()

    old_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, request_stop)
    # Official --json status reports AGGREGATE H/s for all selected devices.
    # Never fabricate per-GPU hashrates by dividing the total.
    args = [str(binary), "--node", cfg["node"], "--address-file", str(address_file),
            "--backend", "cuda", "--devices", ",".join(map(str, selected)), "--json"]
    if cfg["batch"] is not None:
        args += ["--batch", str(cfg["batch"])]
    proc = None
    lock = threading.Lock()

    def consume(stream):
        nonlocal latest, last_status
        for line in stream:
            parsed = accepted_status(line)
            if parsed is not None:
                with lock:
                    latest = parsed
                    last_status = time.time()
                print("TOTAL %d GPUs | %.3f MH/s | shares %s | rejected %s | blocks %s" %
                      (len(selected), float(parsed["hashrate_hs"]) / 1e6,
                       parsed.get("accepted_shares", 0), parsed.get("rejected", 0),
                       parsed.get("accepted_blocks", 0)), flush=True)
            else:
                print(line.rstrip(), flush=True)

    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, bufsize=1)
        reader = threading.Thread(target=consume, args=(proc.stdout,), daemon=True)
        reader.start()
        while not stop.is_set():
            if proc.poll() is not None:
                raise RuntimeError("Official miner stopped with exit code %s" % proc.returncode)
            now = time.time()
            with lock:
                data = latest
                seen = last_status
            fresh = data is not None and now - seen <= STATUS_TTL
            rate = float(data["hashrate_hs"]) if fresh else 0.0
            stats = {"hs": [rate], "hs_units": "hs", "uptime": int(now-started),
                     "ar": [int(data.get("accepted_shares", 0)) if data else 0,
                            int(data.get("rejected", 0)) if data else 0],
                     "algo": "kryptohash", "ver": UPSTREAM}
            # One logical aggregate hash rate is reported; GPU count in separate diagnostic field.
            atomic_json(stats_file, {"updated": now, "khs": rate / 1000.0,
                                     "stats": stats, "gpu_count": len(selected),
                                     "gpu_indices": selected, "accepted_blocks":
                                     int(data.get("accepted_blocks", 0)) if data else 0})
            # Dataset initialization can take significant time on multi-GPU rigs.
            if now - seen > 900:
                raise RuntimeError("No status for 15 minutes; check GPU memory, node, and logs")
            stop.wait(5)
    finally:
        stop.set()
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        atomic_json(stats_file, {"updated": time.time(), "khs": 0, "stats": None})
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["configure", "run", "stats"])
    parser.add_argument("path")
    args = parser.parse_args()
    if args.action == "configure":
        cfg = config_from_env(os.environ)
        atomic_json(args.path, cfg)
        print("Configuration GNR creee: %s; GPUs: %s; aucune cle privee." %
              (cfg["node"], cfg["devices"] if cfg["devices"] is not None else "tous les NVIDIA"))
    elif args.action == "stats":
        khs, stats = read_stats(args.path)
        print(khs)
        print(json.dumps(stats, separators=(",", ":"), allow_nan=False))
    else:
        run_multi(args.path)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print("GNR ERREUR: " + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
