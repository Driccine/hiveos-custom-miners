#!/usr/bin/env python3
"""ORU (RigorChain) — prototype indépendant RGRPOW01, CPU uniquement.

PoW: SHA3-256(b'RGRPOW01' + canonical_header_80).
Le digest est interprété little-endian pour la comparaison de target.
Ce module ne contacte pas de pool ni de noeud et ne soumet pas de shares.
"""
import argparse
import hashlib
from dataclasses import dataclass

DOMAIN = b"RGRPOW01"
HEADER_LENGTH = 80
MAX_NONCE = 0xFFFFFFFF


@dataclass(frozen=True)
class Result:
    nonce: int
    digest: bytes
    attempts: int


def digest_header(header: bytes) -> bytes:
    if len(header) != HEADER_LENGTH:
        raise ValueError("L'en-tête doit faire exactement 80 octets")
    return hashlib.sha3_256(DOMAIN + header).digest()


def meets_target(digest: bytes, target_hex: str) -> bool:
    if len(digest) != 32:
        raise ValueError("Le digest doit faire 32 octets")
    if len(target_hex) != 64:
        raise ValueError("La cible doit avoir 64 caractères hexadécimaux")
    target = int(target_hex, 16)
    return int.from_bytes(digest, "little") <= target


def scan_nonces(header: bytes, target_hex: str, start: int, count: int) -> Result | None:
    if len(header) != HEADER_LENGTH:
        raise ValueError("L'en-tête doit faire exactement 80 octets")
    if not 0 <= start <= MAX_NONCE:
        raise ValueError("Nonce de départ hors de la plage 32 bits")
    if not 1 <= count <= MAX_NONCE + 1:
        raise ValueError("Nombre d'essais hors de la plage 1..2^32")
    if len(target_hex) != 64:
        raise ValueError("La cible doit faire 32 octets en hexadécimal")
    target = int(target_hex, 16)

    preimage = bytearray(DOMAIN + header)
    # Header 76..79 (preimage 84..87) contient le nonce 32-bit little-endian.
    for i in range(count):
        nonce = (start + i) & MAX_NONCE
        preimage[84:88] = nonce.to_bytes(4, "little")
        digest = hashlib.sha3_256(preimage).digest()
        if int.from_bytes(digest, "little") <= target:
            return Result(nonce=nonce, digest=digest, attempts=i + 1)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="ORU RGRPOW01, prototype CPU sans réseau")
    parser.add_argument("--header", required=True, help="80 octets de l'en-tête, 160 caractères hex")
    parser.add_argument("--target", required=True, help="Cible numérique, 64 caractères hex big-endian")
    parser.add_argument("--start", type=int, default=0, help="Nonce initial (0..2^32-1)")
    parser.add_argument("--count", type=int, default=1024, help="Nombre de nonces à essayer")
    args = parser.parse_args()
    header = bytes.fromhex(args.header)
    result = scan_nonces(header, args.target, args.start, args.count)
    if result is None:
        print(f"Aucune solution trouvée parmi {args.count} essais.")
    else:
        print(f"Nonce={result.nonce}  Digest={result.digest.hex()}  Essais={result.attempts}")
        print("Solution locale uniquement : aucun bloc ni share n'a été soumis.")


if __name__ == "__main__":
    main()
