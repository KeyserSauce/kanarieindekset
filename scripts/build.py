"""Bygger site/data.json: alle tal, som hjemmesiden Kanarieindekset viser.

Kør (fra projektmappen):
    python3 scripts/build.py
Kræver pandas og requests. Ingen API-nøgle. Skriver site/data.json og udskriver de vigtigste tal.

Kilder
  1. Danmarks Statistik, LBESK310: lønmodtagere efter branche (DB25) × alder, kvartal. Hentes frisk ved hver
     kørsel via scripts/dst.py (TAL=1020 personer, KØN=TOT). Svaret gemmes i data/raw/LBESK310_<hash>.csv.
  2. data/processed/eksponering_brancher.csv: AI-eksponering pr. branche (Eloundou m.fl. 2024, GPT-4 β)
     og gruppen (mest, middel, mindst, offentlig). Se README for, hvordan den er lavet.
  3. Jobindsats Y25i14 (jobopslag på Jobnet og Jobindex efter stillingsbetegnelse): snapshot i
     data/raw/jobindsats_y25i14_jobopslag.csv.
  4. data/processed/eksponering_stillinger.csv: AI-eksponering pr. stillingsbetegnelse (Eloundou-kvintil
     for stillingens ISCO-4-kode).

Definitioner
  Indeks i beskæftigelsesgraferne = 4-kvartalers glidende gennemsnit / gennemsnit af 2022 × 100.
  Mest eksponerede stillinger = Eloundou-kvintil 4-5.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT = ROOT / "site" / "data.json"
sys.path.insert(0, str(HERE))
from dst import fetch, tableinfo  # noqa: E402

I_DAG = date.today().isoformat()
BASIS = [f"2022K{i}" for i in range(1, 5)]
# Aldersgrupper (15-64 = alle aldre)
ALDRE = {"15-24": ["1524"], "25-34": ["2534"], "35-44": ["3544"], "45-64": ["4554", "5564"],
         "15-64": ["1524", "2534", "3544", "4554", "5564"]}
GRUPPENAVN = {"mest": "Mest AI-eksponerede brancher", "middel": "Middel AI-eksponerede brancher",
              "mindst": "Mindst AI-eksponerede brancher"}
# Korte navne, som siden bruger overalt
KORT = {"A": "Landbrug og fiskeri", "B": "Råstofindvinding", "C": "Industri", "D": "Energiforsyning",
        "E": "Vand og affald", "F": "Byggeri", "G": "Handel", "H": "Transport",
        "I": "Hoteller og restauranter", "J": "Udgivelse og medier", "K": "IT og tele", "L": "Finans og forsikring",
        "M": "Ejendomme", "N": "Rådgivning og forskning", "O": "Administrativ service", "P": "Offentlig administration",
        "Q": "Undervisning", "R": "Sundhed og socialvæsen", "S": "Kultur og fritid", "TUV": "Organisationer og service"}
URL = {"LBESK310": "https://www.statistikbanken.dk/LBESK310"}


def r1(x):
    """1 decimal; NaN -> None (JSON null)."""
    return None if pd.isna(x) else round(float(x), 1)


def heltal(x):
    return None if pd.isna(x) else int(round(float(x)))


def pct(basis, slut):
    return 100 * (slut / basis - 1)


# ------------------------------------------------------------------ 1. eksponeringsgrupper
eks = pd.read_csv(PROC / "eksponering_brancher.csv").set_index("db25").sort_values("elo_beta", ascending=False)
assert len(eks) == 20 and eks.gruppe.isin([*GRUPPENAVN, "offentlig"]).all(), "eksponering_brancher.csv er ikke som ventet"
grupper = {g: list(eks.index[eks.gruppe == g]) for g in GRUPPENAVN}

# ------------------------------------------------------------------ 2. LBESK310 (frisk fra DST)
lb = fetch("LBESK310", refresh=True, TAL="1020", KØN="TOT", BRANCHE1020="*",
           ALDER="1524,2534,3544,4554,5564", Tid="*")
assert lb.INDHOLD.notna().all(), "LBESK310 har tomme celler"
W = pd.concat({g: lb[lb.ALDER.isin(koder)].pivot_table(index="TID", columns="BRANCHE1020", values="INDHOLD", aggfunc="sum")
               for g, koder in ALDRE.items()}, axis=1).swaplevel(axis=1).sort_index()
tider = list(W.index)
SLUT = tider[-4:]
navne = {v["id"]: v["text"].split(" ", 1)[1] for v in
         next(x for x in tableinfo("LBESK310")["variables"] if x["id"] == "BRANCHE1020")["values"]}


def serie(brancher, alder):
    """Kvartalsserie: sum over brancher for én aldersgruppe."""
    return W[[(b, alder) for b in brancher]].sum(axis=1)


def aendring(brancher, alder):
    """(pct.-ændring, gns. 2022, gns. seneste 4 kvt.)"""
    s = serie(brancher, alder)
    b, e = s[BASIS].mean(), s[SLUT].mean()
    return pct(b, e), b, e


# Beskæftigelsesgraferne: 4-kvartalers glidende gns.; de første 3 kvartaler udgår
perioder = tider[3:]
serier, antal = {}, {}
for alder in ALDRE:
    serier[alder], antal[alder] = {}, {}
    for g, brs in {**grupper, "alle": ["A-V"]}.items():
        s = serie(brs, alder)
        ma4 = s.rolling(4).mean()
        serier[alder][g] = [r1(v) for v in (ma4 / s[BASIS].mean() * 100)[perioder]]
        antal[alder][g] = [heltal(v) for v in ma4[perioder]]

# Sammensætning i 2022: andel af hver aldersgruppe i hver eksponeringsgruppe (pct.)
alle_grupper = {**grupper, "offentlig": list(eks.index[eks.gruppe == "offentlig"])}
sammensaetning = {}
for alder in ALDRE:
    niv = {g: serie(brs, alder)[BASIS].mean() for g, brs in alle_grupper.items()}
    tot = sum(niv.values())
    sammensaetning[alder] = {g: r1(100 * v / tot) for g, v in niv.items()}

# Nærbilleder af fire brancher efter alder (to eksponerede, to til sammenligning)
NAERBILLEDER = ["K", "J", "R", "F"]
naerbilleder = {}
for kode in NAERBILLEDER:
    naerbilleder[kode] = {"navn": KORT[kode], "gruppe": eks.loc[kode, "gruppe"], "serier": {}}
    for alder in [a for a in ALDRE if a != "15-64"]:
        s_ = serie([kode], alder)
        naerbilleder[kode]["serier"][alder] = [r1(v) for v in (s_.rolling(4).mean() / s_[BASIS].mean() * 100)[perioder]]

# Én række pr. branche, sorteret efter eksponering
brancher = []
for kode, r in eks.iterrows():
    ung, u22, unu = aendring([kode], "15-24")
    brancher.append({"kode": kode, "navn": navne[kode], "kort": KORT[kode], "gruppe": r.gruppe,
                     "eksponering": round(float(r.elo_beta), 3), "ung_pct": r1(ung),
                     "ung_antal_2022": heltal(u22), "ung_antal_nu": heltal(unu)})

# ------------------------------------------------------------------ 3. jobopslag (Jobindsats Y25i14, snapshot)
# Y25i14 har et brud i stillingstitlerne mellem 2021M09 og 2021M12, så serien starter i 2021M12.
GRUPPE_ISCO = {"IT og software": lambda c: c[:3] in ("251", "252", "351", "352"),
               "Kundeservice": lambda c: c in ("4222", "4225", "5244"),
               "Kontor og administration": lambda c: c.startswith("41") or c == "4311",
               "Kommunikation og journalistik": lambda c: c in ("2432", "2642"),
               "Marketing og reklame": lambda c: c == "2431",
               "Grafisk design og web": lambda c: c in ("2166", "2513")}

y14 = pd.read_csv(RAW / "jobindsats_y25i14_jobopslag.csv")
y14["v"] = pd.to_numeric(y14.vaerdi, errors="coerce").fillna(0)
y14_tot = y14[y14.kategori == "Stillingsbetegnelse i alt"].set_index("periode").v
y14 = y14[y14.kategori.str.startswith("(")].assign(
    kode=lambda d: d.kategori.str.extract(r"^\(([\d.]+)\)")[0],
    isco=lambda d: d.kategori.str.extract(r"^\((\d{4})")[0])
stil = pd.read_csv(PROC / "eksponering_stillinger.csv", dtype={"escostar_kode": str})
y14["q"] = y14.kode.map(dict(zip(stil.escostar_kode, stil.elo_kvintil)))
ji = pd.DataFrame({navn: y14[y14.isco.fillna("").map(f)].groupby("periode").v.sum() for navn, f in GRUPPE_ISCO.items()})
ji["mest"] = y14[y14.q >= 4].groupby("periode").v.sum()
ji["alle brancher"] = y14_tot
ji = ji.sort_index().loc["2021M12":]
BASIS_UDGAVE = "2023M06"                         # opslag fra sep. 2022-feb. 2023, omkring ChatGPT (30.11.2022)
ji = ji / ji.loc[BASIS_UDGAVE] * 100


def vindue(udgave):
    """Udgaven dækker opslag, der er 4-9 måneder gamle (STAR's metode): start, slut og midtpunkt."""
    p = pd.Period(udgave.replace("M", "-"), freq="M")
    return str(p - 9), str(p - 4), str(p - 6)


stillingsgrupper = {
    "udgaver": list(ji.index),
    "vindue": [vindue(u) for u in ji.index],
    "basis": {"udgave": BASIS_UDGAVE, "vindue": vindue(BASIS_UDGAVE)},
    **{k: [r1(v) for v in ji[k]] for k in ji},
}

# ------------------------------------------------------------------ 4. skriv data.json
data = {
    "bygget": I_DAG,
    "kilder": {"LBESK310": {"seneste": tider[-1], "hentet": I_DAG, "url": URL["LBESK310"]}},
    "beskaeftigelse": {"perioder": perioder, "chatgpt": "2022K4",
                       "grupper": {g: {"navn": GRUPPENAVN[g], "brancher": brs} for g, brs in grupper.items()},
                       "serier": serier, "antal": antal,
                       "sammensaetning": sammensaetning, "naerbilleder": naerbilleder},
    "brancher": brancher,
    "stillingsgrupper": stillingsgrupper,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")

# ------------------------------------------------------------------ 5. de vigtigste tal
print(f"site/data.json skrevet ({OUT.stat().st_size / 1024:.0f} KB). LBESK310 til {tider[-1]} (hentet {I_DAG}), "
      f"Y25i14 til {ji.index[-1]}.\n")
print("Ændring i lønmodtagere, gns. 2022 -> gns. " + f"{SLUT[0]}–{SLUT[-1]} (pct.)")
for alder in ALDRE:
    tal = {g: r1(aendring(brs, alder)[0]) for g, brs in {**grupper, "alle": ["A-V"]}.items()}
    print(f"  {alder:<6} " + "  ".join(f"{g} {v:+.1f}" for g, v in tal.items()))
print(f"\nJobopslag, seneste udgave ({ji.index[-1]}), sep. 2022-feb. 2023 = 100")
for k in ji:
    print(f"  {k:<32} {ji[k].iloc[-1]:.1f}")
