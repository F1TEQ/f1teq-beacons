#!/usr/bin/env python3
"""Validation complète du dépôt f1teq-beacons avant publication."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def fail(message: str) -> None:
    raise SystemExit(f"ERREUR : {message}")


def main() -> int:
    full = json.loads((DATA / "beacons.json").read_text(encoding="utf-8"))
    compact_bytes = (DATA / "beacons.min.json").read_bytes()
    compact = json.loads(compact_bytes.decode("utf-8"))
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    manual = json.loads((DATA / "manual_extra.json").read_text(encoding="utf-8"))
    seed = json.loads((DATA / "international_seed.json").read_text(encoding="utf-8"))

    rows = full.get("beacons", [])
    compact_rows = compact.get("d", [])
    keys = [(str(row.get("call", "")).upper(), int(row.get("frequency_hz", 0))) for row in rows]
    ref_count = sum(1 for row in rows if str(row.get("source", "")).upper() == "REF")
    ibp_count = sum(1 for row in rows if "slot" in row)

    if len(seed.get("beacons", [])) < 152: fail("base internationale de secours incomplète")
    if len(manual) < 98: fail("manual_extra.json ne contient pas les 98 entrées REF")
    if len(rows) < 250: fail(f"beacons.json ne contient que {len(rows)} entrées")
    if len(set(keys)) != len(keys): fail("doublons indicatif/fréquence dans beacons.json")
    if ref_count < 98: fail(f"seulement {ref_count} entrées REF")
    if ibp_count != 90: fail(f"{ibp_count} créneaux IBP au lieu de 90")
    if len(compact_rows) != len(rows): fail("nombre différent entre beacons.json et beacons.min.json")
    if compact.get("n") != len(rows): fail("champ n invalide dans beacons.min.json")
    if manifest.get("count") != len(rows): fail("champ count invalide dans manifest.json")
    if manifest.get("size") != len(compact_bytes): fail("taille invalide dans manifest.json")
    if len(compact_bytes) > 120_000: fail("beacons.min.json dépasse la limite firmware de 120 000 octets")
    digest = hashlib.sha256(compact_bytes).hexdigest()
    if manifest.get("sha256") != digest: fail("SHA-256 invalide dans manifest.json")
    if manifest.get("file") != "beacons.min.json": fail("nom de fichier incorrect dans manifest.json")
    if not (DATA.parent / ".github" / "workflows" / "update-beacons.yml").exists():
        fail("workflow GitHub absent")

    print("VALIDATION F1TEQ RÉUSSIE")
    print(f"  Internationales : {len(rows) - ref_count}")
    print(f"  REF             : {ref_count}")
    print(f"  Total           : {len(rows)}")
    print(f"  Créneaux IBP    : {ibp_count}")
    print(f"  Taille          : {len(compact_bytes)}")
    print(f"  SHA-256         : {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
