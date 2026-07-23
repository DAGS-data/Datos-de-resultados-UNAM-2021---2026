#!/usr/bin/env python3
"""Preprocesa los CSV de resultados UNAM (2021-2026) en un data.json
compacto para el dashboard estatico (index.html + app.js)."""

import csv
import json
import math
import unicodedata
from collections import defaultdict
from pathlib import Path

BASE = Path("/Users/diegogalvan/Documents/UNAM_RESULTS")
OUT = Path(__file__).parent / "data.json"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
BIN_WIDTH = 5
BIN_MAX = 120
BIN_EDGES = list(range(0, BIN_MAX + BIN_WIDTH, BIN_WIDTH))  # 0..120 step 5 -> 25 edges / 24 bins
N_BINS = len(BIN_EDGES) - 1

ALL_KEY = "__TODAS__"
ALL_PLANTEL_KEY = "__TODOS__"


def norm_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.upper().strip()


def percentile(sorted_vals, p):
    """Linear interpolation percentile (numpy default 'linear'), p in [0,1]."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    idx = p * (n - 1)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def stats_from_values(values):
    n = len(values)
    if n == 0:
        return None
    vals = sorted(values)
    mean = sum(vals) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in vals) / (n - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    q1 = percentile(vals, 0.25)
    median = percentile(vals, 0.5)
    q3 = percentile(vals, 0.75)
    vmin = vals[0]
    vmax = vals[-1]

    hist = [0] * N_BINS
    for v in vals:
        b = int(v // BIN_WIDTH)
        if b >= N_BINS:
            b = N_BINS - 1
        if b < 0:
            b = 0
        hist[b] += 1

    return {
        "n": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": vmin,
        "q1": round(q1, 2),
        "median": round(median, 2),
        "q3": round(q3, 2),
        "max": vmax,
        "whiskerMin": vmin,
        "whiskerMax": vmax,
        "outliers": [],
        "items": [],
        "histogram": hist,
    }


print("Leyendo archivo agregado (por licenciatura/plantel)...")
agg_path = BASE / "resultados_licenciatura_unam_2021-2022-2023-2024-2025-2026.csv"
# agg[year][licenciatura][plantel_norm] = {oferta, aspirantes, presentaronExamen,
#   seleccionados, aciertosMinimos, plantel_display}
agg = defaultdict(lambda: defaultdict(dict))
plantel_display = {}

with agg_path.open(encoding="utf-8-sig") as fh:
    reader = csv.DictReader(fh)
    for row in reader:
        year = int(row["anio"])
        lic = row["licenciatura"].strip()
        plantel_raw = row["plantel"].strip()
        pkey = norm_key(plantel_raw)
        # prefer accented display name
        if pkey not in plantel_display or (
            any(ord(c) > 127 for c in plantel_raw)
            and not any(ord(c) > 127 for c in plantel_display[pkey])
        ):
            plantel_display[pkey] = plantel_raw

        def to_int(v):
            v = v.strip()
            return int(v) if v.isdigit() else None

        agg[year][lic][pkey] = {
            "oferta": to_int(row["oferta"]),
            "aspirantes": to_int(row["aspirantes"]),
            "presentaronExamen": to_int(row["presentaronExamen"]),
            "seleccionados": to_int(row["seleccionados"]),
            "aciertosMinimos": to_int(row["aciertosMinimos"]),
        }

print("Leyendo archivos individuales por anio...")
# values[year][lic][pkey] = list of aciertos (int)
values = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

for year in YEARS:
    fp = BASE / f"resultados_individuales_unam_{year}.csv"
    print(f"  {fp.name}")
    with fp.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            a = row["aciertos"].strip()
            if not a:
                continue
            try:
                v = int(a)
            except ValueError:
                continue
            lic = row["licenciatura"].strip()
            pkey = norm_key(row["plantel"].strip())
            if pkey not in plantel_display:
                plantel_display[pkey] = row["plantel"].strip()
            values[year][lic][pkey].append(v)

print("Calculando licenciaturas y planteles...")
all_licenciaturas = set()
lic_planteles = defaultdict(set)  # lic -> set of pkey
for year in YEARS:
    for lic, pmap in values[year].items():
        all_licenciaturas.add(lic)
        for pkey in pmap:
            lic_planteles[lic].add(pkey)
    for lic, pmap in agg[year].items():
        all_licenciaturas.add(lic)
        for pkey in pmap:
            lic_planteles[lic].add(pkey)

print(f"Total licenciaturas: {len(all_licenciaturas)}")

output = {
    "meta": {
        "years": YEARS,
        "binEdges": BIN_EDGES,
        "generatedNote": "UNAM resultados individuales y agregados 2021-2026",
    },
    "overall": {},
    "carreras": {},
}

# ---- Overall (todas las carreras, todos los planteles) ----
for year in YEARS:
    all_vals = []
    for lic, pmap in values[year].items():
        for pkey, vlist in pmap.items():
            all_vals.extend(vlist)
    entry = stats_from_values(all_vals) or {}

    tot_aspirantes = tot_presento = tot_oferta = tot_selecc = 0
    minimos = []
    for lic, pmap in agg[year].items():
        for pkey, d in pmap.items():
            tot_aspirantes += d["aspirantes"] or 0
            tot_presento += d["presentaronExamen"] or 0
            tot_oferta += d["oferta"] or 0
            tot_selecc += d["seleccionados"] or 0
            if d["aciertosMinimos"] is not None:
                minimos.append(d["aciertosMinimos"])

    entry["totals"] = {
        "aspirantes": tot_aspirantes,
        "presentaronExamen": tot_presento,
        "oferta": tot_oferta,
        "seleccionados": tot_selecc,
        "aciertosMinimosAvg": round(sum(minimos) / len(minimos), 1) if minimos else None,
        "aciertosMinimosMin": min(minimos) if minimos else None,
        "aciertosMinimosMax": max(minimos) if minimos else None,
    }
    output["overall"][str(year)] = entry

# ---- Per carrera / per plantel ----
for lic in sorted(all_licenciaturas):
    pkeys = sorted(lic_planteles[lic], key=lambda k: plantel_display.get(k, k))
    plantel_names = {pkey: plantel_display.get(pkey, pkey) for pkey in pkeys}

    by_plantel = {}

    # "TODOS" planteles combinados para esta carrera
    todos_by_year = {}
    for year in YEARS:
        vals = []
        for pkey in pkeys:
            vals.extend(values[year].get(lic, {}).get(pkey, []))
        entry = stats_from_values(vals)
        if entry is None:
            entry = {}
        tot_aspirantes = tot_presento = tot_oferta = tot_selecc = 0
        minimos = []
        for pkey in pkeys:
            d = agg[year].get(lic, {}).get(pkey)
            if not d:
                continue
            tot_aspirantes += d["aspirantes"] or 0
            tot_presento += d["presentaronExamen"] or 0
            tot_oferta += d["oferta"] or 0
            tot_selecc += d["seleccionados"] or 0
            if d["aciertosMinimos"] is not None:
                minimos.append(d["aciertosMinimos"])
        entry["totals"] = {
            "aspirantes": tot_aspirantes,
            "presentaronExamen": tot_presento,
            "oferta": tot_oferta,
            "seleccionados": tot_selecc,
            "aciertosMinimosAvg": round(sum(minimos) / len(minimos), 1) if minimos else None,
            "aciertosMinimosMin": min(minimos) if minimos else None,
            "aciertosMinimosMax": max(minimos) if minimos else None,
        }
        todos_by_year[str(year)] = entry
    by_plantel[ALL_PLANTEL_KEY] = todos_by_year

    # Cada plantel individual
    for pkey in pkeys:
        pyear = {}
        for year in YEARS:
            vals = values[year].get(lic, {}).get(pkey, [])
            entry = stats_from_values(vals)
            if entry is None:
                entry = {}
            d = agg[year].get(lic, {}).get(pkey)
            if d:
                entry["totals"] = {
                    "aspirantes": d["aspirantes"] or 0,
                    "presentaronExamen": d["presentaronExamen"] or 0,
                    "oferta": d["oferta"] or 0,
                    "seleccionados": d["seleccionados"] or 0,
                    "aciertosMinimosAvg": d["aciertosMinimos"],
                    "aciertosMinimosMin": d["aciertosMinimos"],
                    "aciertosMinimosMax": d["aciertosMinimos"],
                }
            else:
                entry["totals"] = {
                    "aspirantes": 0, "presentaronExamen": 0, "oferta": 0,
                    "seleccionados": 0, "aciertosMinimosAvg": None,
                    "aciertosMinimosMin": None, "aciertosMinimosMax": None,
                }
            pyear[str(year)] = entry
        by_plantel[pkey] = pyear

    output["carreras"][lic] = {
        "planteles": [{"key": ALL_PLANTEL_KEY, "name": "Todos los planteles"}]
        + [{"key": pkey, "name": plantel_names[pkey]} for pkey in pkeys],
        "byPlantel": by_plantel,
    }

payload = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
OUT.write_text(payload)
print(f"Escrito {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")

# data.js: misma info como variable global, para evitar fetch() y problemas de
# CORS al abrir index.html directamente con file:// en el navegador.
JS_OUT = Path(__file__).parent / "data.js"
JS_OUT.write_text("const UNAM_DATA = " + payload + ";\n")
print(f"Escrito {JS_OUT} ({JS_OUT.stat().st_size / 1e6:.2f} MB)")
