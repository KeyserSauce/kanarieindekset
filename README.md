# Kanarieindekset

Kanarieindekset følger, hvordan beskæftigelsen og jobopslag udvikler sig i brancher og stillinger med forskellig grad af AI-eksponering, og om udviklingen er forskellig for unge og ældre. Inspireret af Stanfords [Canaries Dashboard](https://digitaleconomy.stanford.edu/project/indicators/canaries-dashboard/). Bygger kun på offentlige data fra Danmarks Statistik og Jobindsats.

**Se siden:** https://kanarieindekset.dk

Lavet af Søren Bach Jensen, kandidatstuderende i økonomi (polit) ved Københavns Universitet.

## Genskab tallene

```bash
pip install -r requirements.txt
python3 scripts/build.py
```

Scriptet henter de nyeste tal for lønmodtagere fra Danmarks Statistik (LBESK310), kombinerer dem med filerne i `data/` og skriver `site/data.json`, som siden viser. Til sidst udskriver det de vigtigste tal. GitHub Actions kører det den 5. i hver måned og lægger siden op på ny ([.github/workflows/opdater.yml](.github/workflows/opdater.yml)).

Se siden lokalt:

```bash
python3 -m http.server 8765 --directory site
```

## Filer

| Fil | Indhold |
|---|---|
| `scripts/build.py` | Laver alle tal på siden |
| `scripts/dst.py` | Henter tabeller fra Danmarks Statistiks API |
| `data/processed/eksponering_brancher.csv` | AI-eksponering og gruppe for 20 brancher (DB25) |
| `data/processed/eksponering_stillinger.csv` | AI-eksponering for 1.176 stillingsbetegnelser på Jobnet |
| `data/raw/jobindsats_y25i14_jobopslag.csv` | Jobopslag på Jobnet og Jobindex efter stillingsbetegnelse (Jobindsats Y25i14), hentet 27.09.2026 |
| `data/raw/LBESK310_*.csv` | Det seneste svar fra Danmarks Statistik, så man kan se præcis hvilke tal siden bygger på |
| `site/` | Hjemmesiden (`index.html`) og tallene (`data.json`) |

## Sådan er AI-eksponeringen lavet

**Stillinger.** Eloundou m.fl. (2024, *Science*) giver hver amerikansk stilling en score (GPT-4 β) for, hvor stor en del af arbejdsopgaverne en sprogmodel kan halvere tiden på. Scoren er overført til ISCO-08/DISCO-4 via BLS' nøgler (O*NET-SOC → SOC → ISCO-08) som et uvægtet gennemsnit. Stillingsbetegnelserne på Jobnet har en ISCO-4-kode i deres ESCO-STAR-kode, og hver kode får sin Eloundou-kvintil. "Mest eksponerede" stillinger er kvintil 4–5.

**Brancher.** Scoren pr. DISCO-4 vægtes op til de ni hovedgrupper med antal fuldtidsbeskæftigede i den private sektor (LONS20, 2022). Hver branches score er et gennemsnit over hovedgrupperne, vægtet med branchens stillingsmix (FRA029, private arbejdspladser, 2022). Landbrug findes ikke i FRA029 og bruger i stedet Eurostat (lfsa_eisn2, Danmark 2022). De 17 overvejende private brancher rangeres: top 4 er "mest eksponerede", bund 4 er "mindst eksponerede", og resten er "middel". Offentlig administration, undervisning og sundhed holdes for sig.

## Begrænsninger

Tallene er på brancheniveau, ikke for den enkelte person. Jobopslagene opdateres i hånden, indtil der er en API-nøgle til Jobindsats.
