#!/usr/bin/env python3
"""Teste le constructeur dans une copie temporaire, sans modifier le dépôt."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

source_root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="f1teq_beacons_test_") as temporary:
    test_root = Path(temporary) / "repo"
    shutil.copytree(source_root, test_root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    subprocess.run([
        sys.executable, str(test_root / "scripts" / "build_beacons.py"),
        "--offline", "--version", "TEST-OFFLINE",
        "--generated-utc", "2026-08-03T10:46:00+00:00",
    ], cwd=test_root, check=True)
    subprocess.run([
        sys.executable, str(test_root / "scripts" / "validate_repository.py")
    ], cwd=test_root, check=True)
    manifest = json.loads((test_root / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] >= 250
    assert manifest["size"] <= 120_000
print("TEST HORS LIGNE RÉUSSI")
