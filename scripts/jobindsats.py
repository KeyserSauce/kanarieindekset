"""Henter jobopslag fra Jobindsats' API (y25i14: jobopslag på Jobnet og Jobindex efter stillingsbetegnelse).

Nøglen læses fra miljøvariablen JOBINDSATS_API_KEY eller fra filen .jobindsats_key i projektmappen.
Den må aldrig stå i koden eller i git. Uden nøgle bruges snapshottet i data/raw/.

API: https://api.jobindsats.dk/v3 (vejledning: jobindsats.dk/api/kom-i-gang/brugervejledning-til-version-3/).
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.jobindsats.dk/v3"
ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "raw" / "jobindsats_y25i14_jobopslag.csv"
TABEL, MGROUP, MEASURE = "y25i14", "mgrpy25i14_1", "measi14_1"     # målingen "Jobopslag"


def noegle() -> str | None:
    k = os.environ.get("JOBINDSATS_API_KEY")
    fil = ROOT / ".jobindsats_key"
    if not k and fil.exists():
        k = fil.read_text(encoding="utf-8").strip()
    return k or None


def _get(sti: str, k: str, params: dict) -> requests.Response:
    for forsoeg in range(3):
        r = requests.get(f"{API}/{sti}", headers={"Authorization": f"Bearer {k}"}, params=params, timeout=180)
        if r.status_code < 500:
            break
        time.sleep(10)
    if not r.ok:
        raise RuntimeError(f"Jobindsats {r.status_code}: {r.text[:200]}")
    return r


def perioder(k: str) -> list[str]:
    spec = _get(f"table/{TABEL}", k, {"format": "json"}).json()
    return sorted(v["period_id"] for p in spec["periods"] if p["periodtype_id"] == "M" for v in p["values"])


def hent_y25i14(k: str) -> pd.DataFrame:
    """Alle udgaver, hele landet, alle stillingsbetegnelser (ca. 30.000 celler, langt under grænsen)."""
    params = {f"mgroup.{MGROUP}": MEASURE, "period.M": ",".join(perioder(k)),
              "hierarchy._region": "/", "hierarchy._escostar_rs": "*", "format": "csv"}
    d = pd.read_csv(io.StringIO(_get(f"data/{TABEL}", k, params).content.decode("utf-8-sig")), sep=";")
    return pd.DataFrame({"periode": d["Periode"].astype(str).str.strip(),
                         "kategori": d["Stillingsbetegnelse (ESCOSTAR)"].astype(str).str.strip(),
                         "vaerdi": pd.to_numeric(d["Jobopslag"], errors="coerce")})


def opdater_snapshot() -> str:
    """Henter nye tal, hvis der er en nøgle, og skriver snapshottet. Returnerer en kort status."""
    k = noegle()
    if not k:
        return "Jobindsats: ingen API-nøgle, bruger snapshot"
    ny = hent_y25i14(k)
    tot = ny[ny.kategori == "Stillingsbetegnelse i alt"]
    assert tot.periode.nunique() == ny.periode.nunique() > 20, "Jobindsats-svaret mangler totaler eller perioder"
    ny.to_csv(SNAPSHOT, index=False)
    return f"Jobindsats: hentet {ny.periode.nunique()} udgaver ({ny.periode.min()}–{ny.periode.max()}) via API"
