#!/usr/bin/env python3
"""GNR HiveOS 1.2.0 runtime. Reuses legacy parsing/telemetry helpers, NOT its runner."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fcntl
import gnr as legacy
from gnr import *
from relay import Coordinator, Relay
VERSION = "1.2.0"
legacy.VERSION = VERSION

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
    parser.add_argument("--node-poll", type=float, default=3.0)
    parser.add_argument("--start-delay", type=float, default=1.5)
    parser.add_argument("--cpu-threads", type=int, default=1)
    args = parser.parse_args(shlex.split(env.get("GNR_EXTRA", "")))
    if not math.isfinite(args.node_poll) or not 1.0 <= args.node_poll <= 30.0:
        raise ValueError("--node-poll: de 1 a 30 secondes (defaut 3).")
    if not math.isfinite(args.start_delay) or not 0 <= args.start_delay <= 30:
        raise ValueError("--start-delay: de 0 a 30 secondes.")
    if not 1 <= args.cpu_threads <= 16:
        raise ValueError("--cpu-threads: de 1 a 16.")
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
            "devices": devices, "batch": args.batch,
            "node_poll": args.node_poll, "start_delay": args.start_delay,
            "cpu_threads": args.cpu_threads}


def run(config_path):
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    extra = []
    if cfg.get("devices") is not None:
        extra += ["--devices", ",".join(str(x) for x in cfg["devices"])]
    if cfg.get("batch") is not None:
        extra += ["--batch", str(cfg["batch"])]
    for field, option in (("node_poll", "--node-poll"), ("start_delay", "--start-delay"),
                          ("cpu_threads", "--cpu-threads")):
        if field in cfg:
            extra += [option, str(cfg[field])]
    cfg = config_from_env({"GNR_WALLET": cfg["address"], "GNR_NODE": cfg["node"],
                           "GNR_EXTRA": shlex.join(extra)})
    run_dir = Path(config_path).parent
    with open(str(run_dir / "miner.lock"), "a") as lockfile:
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Une instance GNR fonctionne deja. Arreter l'ancien mineur.")
        run_locked(cfg, run_dir)


def run_locked(cfg, run_dir):
    binary = ROOT / "krypton-miner"
    check_binary(binary)
    probe = subprocess.run([str(binary), "--list-devices", "--json"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=180)
    if probe.returncode:
        raise RuntimeError("Detection CUDA echouee: " + probe.stderr.strip())
    selected = select_devices(json.loads(probe.stdout), cfg["devices"])
    address_file = run_dir / "address.txt"
    address_file.write_text(cfg["address"] + "\n", encoding="ascii")
    os.chmod(str(address_file), 0o600)
    stop = threading.Event()
    coordinator = Coordinator(cfg["node"], cfg["address"], stop, poll=cfg["node_poll"],
                              log=lambda message: print(message, flush=True))
    info = coordinator.read("/v1/info")
    if info.get("network", "mainnet") != "mainnet":
        raise RuntimeError("Le noeud n'est pas sur mainnet.")
    if "chain_id" in info and info["chain_id"] != "genoryn-krypton-mainnet-1":
        raise RuntimeError("Identifiant de chaine inattendu.")
    relay = Relay(coordinator)
    child_cfg = dict(cfg)
    child_cfg["node"] = relay.start()
    buses = cuda_buses()
    states, processes, birth = {}, [], {}
    lock = threading.Lock()
    started = time.time()
    stats_file = run_dir / "stats.json"
    print("GNR HiveOS %s | %s GPU paralleles | relais partage | template >= %.1fs" %
          (VERSION, len(selected), cfg["node_poll"]), flush=True)
    print("Noeud %s | hauteur %s | GPU %s" %
          (cfg["node"], info.get("height", "?"), ",".join(map(str, selected))), flush=True)

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
                # Never print the loopback relay token from the upstream banner.
                print("GPU %s | %s" % (index, line.rstrip().replace(child_cfg["node"], "[local-relay]")), flush=True)

    old_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, request_stop)
    env = dict(os.environ)
    env["RAYON_NUM_THREADS"] = str(cfg["cpu_threads"])
    last_report = time.monotonic()
    try:
        for index in selected:
            if stop.is_set():
                break
            proc = subprocess.Popen(command(binary, child_cfg, address_file, index),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, bufsize=1, env=env)
            processes.append((index, proc))
            birth[index] = time.time()
            threading.Thread(target=consume, args=(index, proc), daemon=True).start()
            # Initialisation etalee: pas de demarrage CPU simultane des 12 caches.
            stop.wait(cfg["start_delay"])
        while not stop.is_set():
            for index, proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError("Mineur GPU %s arrete (code %s)." % (index, proc.returncode))
            now = time.time()
            with lock:
                saved = dict(states)
            value = snapshot(saved, selected, buses, telemetry(), started, now)
            value["wrapper_version"] = VERSION
            value["relay"] = coordinator.metrics()
            atomic_json(stats_file, value)
            if time.monotonic() - last_report >= 30:
                m = value["relay"]
                print("GNR RELAY | templates %s | cache %s | HTTP429 %s | pause %.1fs" %
                      (m.get("template_requests", 0), m.get("template_cache_hits", 0),
                       m.get("upstream_429", 0), m["backoff_seconds"]), flush=True)
                last_report = time.monotonic()
            for index in selected:
                seen = saved.get(index, {}).get("seen", birth.get(index, started))
                if now - seen > 900:
                    raise RuntimeError("GPU %s: aucune statistique depuis 15 min." % index)
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
        relay.close()
        atomic_json(stats_file, {"updated": time.time(), "khs": 0, "stats": None,
                                 "wrapper_version": VERSION, "relay": coordinator.metrics()})
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
        run(args.path)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print("GNR ERREUR: " + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
