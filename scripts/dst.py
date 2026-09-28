"""Små hjælpefunktioner til Danmarks Statistiks åbne API (api.statbank.dk).

Brug:
    from dst import fetch, tableinfo
    df = fetch("LBESK310", BRANCHE1020="*", ALDER="*", Tid="*")

Svar gemmes i data/raw/, så gentagne kørsler ikke rammer API'et unødigt.
Brug refresh=True for at hente på ny.
"""

import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import requests

API = "https://api.statbank.dk/v1"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def tableinfo(table: str) -> dict:
    r = requests.get(f"{API}/tableinfo", params={"id": table, "lang": "da", "format": "JSON"}, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch(table: str, refresh: bool = False, **variables: str) -> pd.DataFrame:
    """Hent en tabel som DataFrame med kolonnerne fra CSV-svaret (koder, ikke tekster).

    variables: VAR="kode1,kode2" eller VAR="*" for alle værdier.
    Variabler, som DST kræver, men som ikke er angivet, sættes til deres første
    værdi (typisk "I alt").
    """
    for v in tableinfo(table)["variables"]:
        if v["id"] not in variables and not v["elimination"]:
            variables[v["id"]] = v["values"][0]["id"]
    body = {
        "table": table,
        "format": "CSV",
        "lang": "da",
        "valuePresentation": "Code",
        "variables": [{"code": k, "values": v.split(",")} for k, v in variables.items()],
    }
    key = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:10]
    path = RAW / f"{table}_{key}.csv"
    if path.exists() and not refresh:
        text = path.read_text(encoding="utf-8")
    else:
        r = requests.post(f"{API}/data", json=body, timeout=300)
        if not r.ok:
            raise RuntimeError(f"DST {table}: {r.status_code} {r.text[:300]}")
        text = r.content.decode("utf-8-sig")
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    df = pd.read_csv(io.StringIO(text), sep=";", dtype=str)
    df["INDHOLD"] = pd.to_numeric(df["INDHOLD"].str.replace(",", "."), errors="coerce")
    return df


if __name__ == "__main__":
    info = tableinfo("LBESK310")
    print(info["text"], "| seneste:", info["variables"][-1]["values"][-1]["text"])
    print({v["id"]: len(v["values"]) for v in info["variables"]})
    df = fetch("LBESK310", TAL="*", ALDER="*", Tid="2025K4")
    print(df.head())
