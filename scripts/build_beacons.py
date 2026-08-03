#!/usr/bin/env python3
"""Construit la base complète de balises F1TEQ.

Principes de sécurité :
- la base internationale de secours est toujours disponible localement ;
- la source IARU Région 1 est interrogée en ligne, mais une panne ne détruit rien ;
- les 98 entrées REF sont toujours réinjectées et prioritaires ;
- les 18 créneaux IBP sur 5 bandes sont toujours conservés ;
- aucune base de moins de 250 couples indicatif/fréquence n'est publiée.

Le script utilise uniquement la bibliothèque standard Python.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEED_PATH = DATA / "international_seed.json"
MANUAL_PATH = DATA / "manual_extra.json"
FULL_PATH = DATA / "beacons.json"
COMPACT_PATH = DATA / "beacons.min.json"
MANIFEST_PATH = DATA / "manifest.json"

IARU_CSV_URL = "https://iaru-r1-c5-beacons.org/wp-content/uploads/beacons.csv"
MINIMUM_INTERNATIONAL = 152
MINIMUM_IARU = 50
MINIMUM_REF = 98
MINIMUM_TOTAL = 250
EXPECTED_IBP_SLOTS = 90
MAX_COMPACT_BYTES = 110_000  # marge sous la limite firmware de 120 000 octets

IBP_SLOTS = {
    "4U1UN": 1, "VE8AT": 2, "W6WX": 3, "KH6RS": 4,
    "ZL6B": 5, "VK6RBP": 6, "JA2IGY": 7, "RR9O": 8,
    "VR2B": 9, "4S7B": 10, "ZS6DN": 11, "5Z4B": 12,
    "4X6TU": 13, "OH2B": 14, "CS3B": 15, "LU4AA": 16,
    "OA4B": 17, "YV5B": 18,
}
IBP_FREQUENCIES = {14_100_000, 18_110_000, 21_150_000, 24_930_000, 28_200_000}

STATUS_CODES = {
    "-1": "inconnu",
    "0": "inactif/maintenance",
    "1": "actif",
    "2": "proposé/planifié",
}

SOURCES = [
    {
        "id": "IARU-R1",
        "name": "IARU Region 1 VHF and UP coordinated beacons database",
        "url": IARU_CSV_URL,
        "scope": "Région 1, VHF/UHF/SHF, liste coordonnée",
    },
    {
        "id": "NCDXF-IBP",
        "name": "NCDXF/IARU International Beacon Project",
        "url": "https://www.ncdxf.org/beacon/",
        "scope": "18 sites mondiaux sur 14.100, 18.110, 21.150, 24.930 et 28.200 MHz",
    },
    {
        "id": "REF",
        "name": "Réseau des Émetteurs Français — liste des balises radioamateur",
        "url": "https://www.r-e-f.org/index.php?option=com_content&view=article&id=700&Itemid=435",
        "scope": "France métropolitaine et territoires ultramarins, HF/VHF/UHF/SHF",
    },
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"ERREUR : lecture JSON impossible pour {path}: {exc}") from exc


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    # Corrections connues provenant d'anciens exports mal décodés.
    replacements = {
        "BjĂ¸rnĂ¸ya": "Bjørnøya",
        "SchĂ¶nwalde": "Schönwalde",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    # Corrige ensuite les séquences typiques d'un UTF-8 relu en latin-1.
    if any(marker in text for marker in ("Ã", "Â", "Ă")):
        for encoding in ("latin-1", "cp1252"):
            try:
                repaired = text.encode(encoding).decode("utf-8")
                if repaired.count("�") == 0:
                    text = repaired
                    break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    return text


def to_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            value = value.strip().replace(" ", "").replace(",", ".")
            return int(round(float(value)))
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.strip().replace(" ", "").replace(",", ".")
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def maidenhead_to_latlon(locator: str) -> tuple[float, float] | None:
    """Retourne le centre d'un locator Maidenhead pair de 2 à 10 caractères."""
    loc = re.sub(r"\s+", "", locator.upper())
    if len(loc) < 2 or len(loc) > 10 or len(loc) % 2:
        return None
    lon = -180.0
    lat = -90.0
    lon_size = 20.0
    lat_size = 10.0
    try:
        for pair_index in range(len(loc) // 2):
            a, b = loc[pair_index * 2], loc[pair_index * 2 + 1]
            if pair_index == 0:
                if not ("A" <= a <= "R" and "A" <= b <= "R"):
                    return None
                lon += (ord(a) - 65) * lon_size
                lat += (ord(b) - 65) * lat_size
            elif pair_index % 2 == 1:
                if not (a.isdigit() and b.isdigit()):
                    return None
                lon_size /= 10.0
                lat_size /= 10.0
                lon += int(a) * lon_size
                lat += int(b) * lat_size
            else:
                if not ("A" <= a <= "X" and "A" <= b <= "X"):
                    return None
                lon_size /= 24.0
                lat_size /= 24.0
                lon += (ord(a) - 65) * lon_size
                lat += (ord(b) - 65) * lat_size
        return round(lat + lat_size / 2.0, 6), round(lon + lon_size / 2.0, 6)
    except Exception:
        return None


def band_from_frequency(frequency_hz: int) -> str:
    mhz = frequency_hz / 1_000_000.0
    if 13.9 <= mhz < 14.5: return "20 m"
    if 17.9 <= mhz < 18.3: return "17 m"
    if 20.9 <= mhz < 21.6: return "15 m"
    if 24.7 <= mhz < 25.1: return "12 m"
    if 28.0 <= mhz < 30.0: return "10 m"
    if 49.0 <= mhz < 54.0: return "6 m"
    if 69.0 <= mhz < 71.0: return "4 m"
    if 143.0 <= mhz < 148.0: return "2 m"
    if 420.0 <= mhz < 450.0: return "70 cm"
    if 1_200.0 <= mhz < 1_400.0: return "23 cm"
    if 2_200.0 <= mhz < 2_500.0: return "13 cm"
    if 3_300.0 <= mhz < 3_600.0: return "9 cm"
    if 5_600.0 <= mhz < 6_000.0: return "5 cm"
    if 10_000.0 <= mhz < 10_600.0: return "3 cm"
    if 23_000.0 <= mhz < 25_000.0: return "1,2 cm"
    if 46_000.0 <= mhz < 48_000.0: return "6 mm"
    if 75_000.0 <= mhz < 82_000.0: return "4 mm"
    if mhz >= 1_000.0: return f"{mhz / 1_000.0:g} GHz"
    return f"{mhz:g} MHz"


def normalize_status(raw: Any) -> tuple[int, str]:
    value = clean_text(raw)
    folded = value.casefold()
    if not value:
        return 1, "Operational"
    if any(token in folded for token in ("non op", "not op", "qrt", "inactive", "maintenance", "off air")):
        return 0, value
    if any(token in folded for token in ("propos", "planned", "planifi", "construction", "test")):
        return 2, value
    if any(token in folded for token in ("operational", "active", "on air", "ok")):
        return 1, value
    return -1, value


def normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    call = clean_text(raw.get("call")).upper()
    frequency = to_int(raw.get("frequency_hz"))
    if not call or frequency <= 0:
        raise ValueError(f"entrée invalide: indicatif={call!r}, fréquence={frequency!r}")
    locator = clean_text(raw.get("locator")).upper()
    coords = maidenhead_to_latlon(locator)
    lat = to_float(raw.get("lat"), coords[0] if coords else 0.0)
    lon = to_float(raw.get("lon"), coords[1] if coords else 0.0)
    row = {
        "call": call,
        "frequency_hz": frequency,
        "band": clean_text(raw.get("band")) or band_from_frequency(frequency),
        "locator": locator,
        "country": clean_text(raw.get("country")).upper(),
        "region": clean_text(raw.get("region")),
        "city": clean_text(raw.get("city")),
        "lat": lat,
        "lon": lon,
        "status": to_int(raw.get("status"), -1),
        "status_text": clean_text(raw.get("status_text")),
        "mode": clean_text(raw.get("mode")),
        "power_w": clean_text(raw.get("power_w")),
        "antenna": clean_text(raw.get("antenna")),
        "direction": clean_text(raw.get("direction")),
        "source": clean_text(raw.get("source")),
        "source_updated": clean_text(raw.get("source_updated")),
    }
    if call in IBP_SLOTS and frequency in IBP_FREQUENCIES:
        row["slot"] = IBP_SLOTS[call]
    return row


def row_key(row: dict[str, Any]) -> tuple[str, int]:
    return row["call"], row["frequency_hz"]


def normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).casefold())


def find_value(row: dict[str, str], *aliases: str) -> str:
    normalized = {normalized_header(k): v for k, v in row.items() if k is not None}
    for alias in aliases:
        key = normalized_header(alias)
        if key in normalized:
            return clean_text(normalized[key])
    return ""


def parse_frequency_khz(value: str) -> int:
    text = clean_text(value).replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.+-]", "", text)
    try:
        qrg = float(text)
    except ValueError:
        return 0
    # La base IARU utilise QRG en kHz.
    return int(round(qrg * 1_000.0))


def decode_csv_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def fetch_iaru_rows(seed_by_key: dict[tuple[str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        IARU_CSV_URL,
        headers={
            "User-Agent": "F1TEQ-Beacon-Updater/2.0",
            "Accept": "text/csv,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        payload = response.read(8_000_000)
    text = decode_csv_bytes(payload)
    if len(text) < 100:
        raise RuntimeError("fichier IARU trop court")

    sample = text[:4096]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise RuntimeError("en-tête CSV IARU absent")

    parsed: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date().isoformat()
    for source_row in reader:
        call = find_value(source_row, "Callsign", "Call", "Indicatif").upper()
        frequency = parse_frequency_khz(find_value(source_row, "QRG", "Frequency", "Frequence", "Fréquence"))
        locator = find_value(source_row, "Locator", "Loc", "Maidenhead").upper()
        if not call or frequency <= 0 or not locator:
            continue

        old = seed_by_key.get((call, frequency), {})
        status_code, status_text = normalize_status(find_value(source_row, "Status", "Etat", "État"))
        key_mode = find_value(source_row, "Key", "Mode", "Emission")
        mgm = find_value(source_row, "MGM", "Machine generated mode")
        mode = "/".join(part for part in (key_mode, mgm) if part)
        locator_coords = maidenhead_to_latlon(locator)

        row = normalize_row({
            "call": call,
            "frequency_hz": frequency,
            "band": band_from_frequency(frequency),
            "locator": locator,
            "country": find_value(source_row, "Country", "Pays", "DXCC") or old.get("country", ""),
            "region": find_value(source_row, "Region", "State", "Department", "Département") or old.get("region", ""),
            "city": find_value(source_row, "Nearest Town", "Town", "City", "QTH", "Location", "Site") or old.get("city", ""),
            "lat": locator_coords[0] if locator_coords else old.get("lat", 0.0),
            "lon": locator_coords[1] if locator_coords else old.get("lon", 0.0),
            "status": status_code,
            "status_text": status_text,
            "mode": mode or old.get("mode", ""),
            "power_w": find_value(source_row, "Power", "ERP", "Power ERP") or old.get("power_w", ""),
            "antenna": find_value(source_row, "Antenna", "Aerial") or old.get("antenna", ""),
            "direction": find_value(source_row, "Pattern", "Heading", "Direction") or old.get("direction", ""),
            "source": "IARU-R1",
            "source_updated": find_value(source_row, "Last Update", "Updated", "Date") or today,
        })
        parsed.append(row)

    unique = {row_key(row): row for row in parsed}
    rows = list(unique.values())
    if len(rows) < MINIMUM_IARU:
        raise RuntimeError(f"seulement {len(rows)} entrées IARU valides")
    return rows


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "c": row["call"], "f": row["frequency_hz"], "b": row["band"],
        "g": row["locator"], "y": row["country"], "r": row["region"],
        "n": row["city"], "a": row["lat"], "o": row["lon"],
        "s": row["status"], "m": row["mode"], "u": row["source"],
    }
    if "slot" in row:
        compact["q"] = row["slot"]
    return compact




def compact_size_for_rows(rows: list[dict[str, Any]]) -> int:
    probe = {
        "v": 1,
        "t": "2099-12-31T23:59:59+00:00",
        "n": len(rows),
        "k": {
            "c": "call", "f": "frequency_hz", "b": "band",
            "g": "locator", "y": "country", "r": "region",
            "n": "city", "a": "lat", "o": "lon", "s": "status",
            "m": "mode", "u": "source", "q": "ibp_slot",
        },
        "d": [compact_row(row) for row in rows],
    }
    return len(json.dumps(probe, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def limit_new_rows_for_esp32(
    merged: dict[tuple[str, int], dict[str, Any]],
    protected_keys: set[tuple[str, int]],
) -> dict[tuple[str, int], dict[str, Any]]:
    """Conserve toujours le socle 250 et ajoute les nouveautés dans la limite ESP32."""
    protected = [merged[key] for key in protected_keys if key in merged]
    protected.sort(key=lambda row: (
        row["frequency_hz"], row["locator"], row["country"],
        row["region"] or row["city"], row["call"],
    ))
    if compact_size_for_rows(protected) > MAX_COMPACT_BYTES:
        raise SystemExit("ERREUR : le socle protégé dépasse déjà la taille compatible ESP32.")

    candidates = [row for key, row in merged.items() if key not in protected_keys]
    candidates.sort(key=lambda row: (
        0 if row["status"] == 1 else 1,
        row["frequency_hz"], row["locator"], row["call"],
    ))
    selected = list(protected)
    ignored = 0
    for row in candidates:
        trial = selected + [row]
        if compact_size_for_rows(trial) <= MAX_COMPACT_BYTES:
            selected.append(row)
        else:
            ignored += 1
    if ignored:
        print(
            f"AVERTISSEMENT : {ignored} nouvelle(s) entrée(s) IARU non ajoutée(s) "
            f"afin de rester sous {MAX_COMPACT_BYTES} octets pour l'ESP32."
        )
    return {row_key(row): row for row in selected}

def rows_digest(rows: Iterable[dict[str, Any]]) -> str:
    payload = json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def existing_content_digest() -> str:
    if not FULL_PATH.exists():
        return ""
    try:
        document = load_json(FULL_PATH)
        rows = [normalize_row(row) for row in document.get("beacons", [])]
        rows.sort(key=lambda row: (row["frequency_hz"], row["locator"], row["country"], row["region"] or row["city"], row["call"]))
        return rows_digest(rows)
    except Exception:
        return ""


def choose_version(changed: bool, forced_version: str | None, forced_time: str | None) -> tuple[str, str]:
    if forced_time:
        generated_utc = forced_time
        parsed = datetime.fromisoformat(forced_time.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc).replace(microsecond=0)
        generated_utc = parsed.isoformat()

    if forced_version:
        return forced_version, generated_utc

    if not changed and MANIFEST_PATH.exists():
        try:
            old = load_json(MANIFEST_PATH)
            if old.get("version") and old.get("generated_utc"):
                return str(old["version"]), str(old["generated_utc"])
        except Exception:
            pass
    return parsed.strftime("%Y%m%d-%H%M%S"), generated_utc


def validate(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    unique_count = len({row_key(row) for row in rows})
    ref_count = sum(1 for row in rows if row["source"].upper() == "REF")
    international_count = len(rows) - ref_count
    ibp_slot_count = sum(1 for row in rows if "slot" in row)
    if unique_count != len(rows):
        raise SystemExit(f"ERREUR : {len(rows) - unique_count} doublon(s) indicatif/fréquence.")
    if ref_count < MINIMUM_REF:
        raise SystemExit(f"ERREUR : seulement {ref_count} entrées REF, minimum {MINIMUM_REF}.")
    if international_count < MINIMUM_INTERNATIONAL:
        raise SystemExit(f"ERREUR : seulement {international_count} entrées internationales, minimum {MINIMUM_INTERNATIONAL}.")
    if len(rows) < MINIMUM_TOTAL:
        raise SystemExit(f"ERREUR : base finale de {len(rows)} entrées, minimum {MINIMUM_TOTAL}.")
    if ibp_slot_count != EXPECTED_IBP_SLOTS:
        raise SystemExit(f"ERREUR : {ibp_slot_count} créneaux IBP, attendu {EXPECTED_IBP_SLOTS}.")
    for row in rows:
        if row["frequency_hz"] <= 0:
            raise SystemExit(f"ERREUR : fréquence invalide pour {row['call']}.")
        if not row["locator"] and not (-90 <= row["lat"] <= 90 and -180 <= row["lon"] <= 180):
            raise SystemExit(f"ERREUR : position inutilisable pour {row['call']}.")
    return international_count, ref_count, ibp_slot_count


def build(offline: bool, forced_version: str | None, forced_time: str | None) -> None:
    seed = load_json(SEED_PATH)
    manual = load_json(MANUAL_PATH)
    if not isinstance(seed, dict) or not isinstance(seed.get("beacons"), list):
        raise SystemExit("ERREUR : data/international_seed.json invalide.")
    if not isinstance(manual, list) or len(manual) < MINIMUM_REF:
        raise SystemExit("ERREUR : data/manual_extra.json doit contenir au moins 98 entrées REF.")

    seed_rows = [normalize_row(row) for row in seed["beacons"]]
    seed_by_key = {row_key(row): row for row in seed_rows}
    international = dict(seed_by_key)

    if offline:
        print("Mode hors ligne : utilisation de la base internationale de secours.")
    else:
        try:
            fetched = fetch_iaru_rows(seed_by_key)
            for row in fetched:
                international[row_key(row)] = row
            print(f"Source IARU téléchargée : {len(fetched)} entrées valides.")
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            print(f"AVERTISSEMENT : source IARU indisponible ({exc}). Base de secours conservée.")

    merged = dict(international)
    manual_keys: set[tuple[str, int]] = set()
    for raw in manual:
        row = normalize_row(raw)
        row["source"] = "REF"
        manual_keys.add(row_key(row))
        merged[row_key(row)] = row

    protected_keys = set(seed_by_key) | manual_keys
    merged = limit_new_rows_for_esp32(merged, protected_keys)

    rows = list(merged.values())
    rows.sort(key=lambda row: (
        row["frequency_hz"], row["locator"], row["country"],
        row["region"] or row["city"], row["call"],
    ))
    international_count, ref_count, ibp_count = validate(rows)

    new_digest = rows_digest(rows)
    changed = new_digest != existing_content_digest()
    version, generated_utc = choose_version(changed, forced_version, forced_time)

    full_document = {
        "schema": 1,
        "generated_utc": generated_utc,
        "count": len(rows),
        "status_codes": STATUS_CODES,
        "sources": SOURCES,
        "beacons": rows,
    }
    FULL_PATH.write_text(json.dumps(full_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    compact_document = {
        "v": 1,
        "t": generated_utc,
        "n": len(rows),
        "k": {
            "c": "call", "f": "frequency_hz", "b": "band",
            "g": "locator", "y": "country", "r": "region",
            "n": "city", "a": "lat", "o": "lon", "s": "status",
            "m": "mode", "u": "source", "q": "ibp_slot",
        },
        "d": [compact_row(row) for row in rows],
    }
    compact_bytes = json.dumps(compact_document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    COMPACT_PATH.write_bytes(compact_bytes)
    compact_sha = hashlib.sha256(compact_bytes).hexdigest()

    manifest = {
        "schema": 1,
        "version": version,
        "generated_utc": generated_utc,
        "count": len(rows),
        "size": len(compact_bytes),
        "sha256": compact_sha,
        "file": "beacons.min.json",
        "minimum_esp32_free_space": len(compact_bytes) * 2 + 16_384,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Base F1TEQ construite et contrôlée")
    print(f"  Version                    : {version}")
    print(f"  Entrées internationales    : {international_count}")
    print(f"  Entrées françaises / REF   : {ref_count}")
    print(f"  Total                      : {len(rows)}")
    print(f"  Entrées avec créneau IBP   : {ibp_count}")
    print(f"  Taille ESP32               : {len(compact_bytes)} octets")
    print(f"  SHA-256 ESP32              : {compact_sha}")
    print(f"  Données modifiées          : {'OUI' if changed else 'NON'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Construire la base complète F1TEQ de balises.")
    parser.add_argument("--offline", action="store_true", help="Ne pas interroger la source IARU en ligne.")
    parser.add_argument("--version", help="Forcer la version du manifeste.")
    parser.add_argument("--generated-utc", help="Forcer la date ISO UTC du manifeste.")
    args = parser.parse_args()
    build(args.offline, args.version, args.generated_utc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
