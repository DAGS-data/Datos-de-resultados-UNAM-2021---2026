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


def wasserstein1_int(vals_a, vals_b, max_val=BIN_MAX):
    """Distancia de Wasserstein-1 exacta entre dos muestras con soporte
    entero en [0, max_val]. Para variables discretas de este tipo,
    W1 = sum_k |CDF_a(k) - CDF_b(k)| para k en [0, max_val-1] (ancho de
    intervalo = 1), equivalente a la formula clasica basada en el area
    entre las dos funciones de distribucion acumulada."""
    if not vals_a or not vals_b:
        return None
    na, nb = len(vals_a), len(vals_b)
    counts_a = [0] * (max_val + 1)
    counts_b = [0] * (max_val + 1)
    for v in vals_a:
        counts_a[v] += 1
    for v in vals_b:
        counts_b[v] += 1
    dist = 0.0
    cum_a = cum_b = 0
    for k in range(max_val):  # 0..max_val-1, cada intervalo [k, k+1) tiene ancho 1
        cum_a += counts_a[k]
        cum_b += counts_b[k]
        dist += abs(cum_a / na - cum_b / nb)
    return dist


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

    n_lt5 = sum(1 for v in vals if v < 5)

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
        "nLt5": n_lt5,
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

# ---- Ranking de cambio de distribucion 2025 -> 2026 (Wasserstein-1) ----
# Solo se compara cuando la combinacion carrera+plantel tiene datos en AMBOS
# anios: las carreras nuevas de 2026 (o las que desaparecieron) no tienen
# contraparte en 2025 y quedan fuera automaticamente, sin necesidad de una
# lista especial de carreras nuevas.
MIN_N_WASSERSTEIN = 50  # evita que combinaciones muy chicas (ruido muestral) dominen el ranking
YEAR_A, YEAR_B = 2025, 2026

wasserstein_rows = []
for lic in sorted(all_licenciaturas):
    for pkey in lic_planteles[lic]:
        vals_a = values[YEAR_A].get(lic, {}).get(pkey, [])
        vals_b = values[YEAR_B].get(lic, {}).get(pkey, [])
        if len(vals_a) < MIN_N_WASSERSTEIN or len(vals_b) < MIN_N_WASSERSTEIN:
            continue
        dist = wasserstein1_int(vals_a, vals_b)
        if dist is None:
            continue
        stats_a = stats_from_values(vals_a)
        stats_b = stats_from_values(vals_b)
        wasserstein_rows.append({
            "licenciatura": lic,
            "plantel": plantel_display.get(pkey, pkey),
            "distance": round(dist, 2),
            "n2025": stats_a["n"],
            "n2026": stats_b["n"],
            "medianDiff": round(stats_b["median"] - stats_a["median"], 1),
            "meanDiff": round(stats_b["mean"] - stats_a["mean"], 2),
        })

wasserstein_rows.sort(key=lambda r: r["distance"], reverse=True)
output["wasserstein2025_2026"] = {
    "minN": MIN_N_WASSERSTEIN,
    "yearA": YEAR_A,
    "yearB": YEAR_B,
    "top": wasserstein_rows,
}
print(f"Wasserstein: {len(wasserstein_rows)} combinaciones comparables (n>={MIN_N_WASSERSTEIN} en ambos anios)")

payload = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
OUT.write_text(payload)
print(f"Escrito {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")

# data.js: misma info como variable global, para evitar fetch() y problemas de
# CORS al abrir index.html directamente con file:// en el navegador.
JS_OUT = Path(__file__).parent / "data.js"
JS_OUT.write_text("const UNAM_DATA = " + payload + ";\n")
print(f"Escrito {JS_OUT} ({JS_OUT.stat().st_size / 1e6:.2f} MB)")


# =====================================================================
# SUAYED — misma idea que arriba, pero solo hay archivos de resultados
# INDIVIDUALES (aún no se corrió el scraper de resumen por licenciatura/
# plantel para SUAYED), así que "oferta" y "aciertosMinimos" no están
# disponibles: se dejan en 0/None. "aspirantes", "presentaronExamen" y
# "seleccionados" sí se pueden derivar de los datos individuales
# (aspirantes = filas totales, presentaronExamen = filas con aciertos,
# seleccionados = filas con acreditado == "S"), y son los únicos totales
# que usa la UI (app.js nunca lee totals.oferta ni aciertosMinimos*).
# =====================================================================
print("\n=== SUAYED ===")
SUAYED_DIR = BASE / "Suayed"
SUAYED_JSON_OUT = Path(__file__).parent / "data_suayed.json"
SUAYED_JS_OUT = Path(__file__).parent / "data_suayed.js"


def make_totals(aspirantes, presento, selecc):
    return {
        "aspirantes": aspirantes,
        "presentaronExamen": presento,
        "oferta": 0,
        "seleccionados": selecc,
        "aciertosMinimosAvg": None,
        "aciertosMinimosMin": None,
        "aciertosMinimosMax": None,
    }


suayed_values = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # [year][lic][pkey] -> aciertos
suayed_aspirantes = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # [year][lic][pkey] -> filas totales
suayed_seleccionados = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # [year][lic][pkey] -> acreditado==S
suayed_plantel_display = {}

suayed_files = sorted(SUAYED_DIR.glob("resultados_individuales_unam_suayed_*.csv"))
print(f"Leyendo archivos SUAYED: {[f.name for f in suayed_files]}")
for fp in suayed_files:
    with fp.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["anio"])
            if year not in YEARS:
                continue
            lic = row["licenciatura"].strip()
            plantel_raw = row["plantel"].strip()
            pkey = norm_key(plantel_raw)
            if pkey not in suayed_plantel_display or (
                any(ord(c) > 127 for c in plantel_raw)
                and not any(ord(c) > 127 for c in suayed_plantel_display[pkey])
            ):
                suayed_plantel_display[pkey] = plantel_raw

            suayed_aspirantes[year][lic][pkey] += 1
            if row["acreditado"].strip() == "S":
                suayed_seleccionados[year][lic][pkey] += 1

            a = row["aciertos"].strip()
            if a:
                try:
                    suayed_values[year][lic][pkey].append(int(a))
                except ValueError:
                    pass

print("Calculando licenciaturas y planteles SUAYED...")
suayed_all_licenciaturas = set()
suayed_lic_planteles = defaultdict(set)
for year in YEARS:
    for lic, pmap in suayed_aspirantes[year].items():
        suayed_all_licenciaturas.add(lic)
        for pkey in pmap:
            suayed_lic_planteles[lic].add(pkey)

print(f"Total licenciaturas SUAYED: {len(suayed_all_licenciaturas)}")

output_suayed = {
    "meta": {
        "years": YEARS,
        "binEdges": BIN_EDGES,
        "generatedNote": "UNAM resultados individuales SUAYED 2021-2026 (oferta y aciertos minimos no disponibles)",
    },
    "overall": {},
    "carreras": {},
}

# ---- Overall (todas las carreras, todos los planteles) ----
for year in YEARS:
    all_vals = []
    tot_aspirantes = tot_presento = tot_selecc = 0
    for lic, pmap in suayed_aspirantes[year].items():
        for pkey, cnt in pmap.items():
            tot_aspirantes += cnt
    for lic, pmap in suayed_values[year].items():
        for pkey, vlist in pmap.items():
            all_vals.extend(vlist)
            tot_presento += len(vlist)
    for lic, pmap in suayed_seleccionados[year].items():
        for pkey, cnt in pmap.items():
            tot_selecc += cnt

    entry = stats_from_values(all_vals) or {}
    entry["totals"] = make_totals(tot_aspirantes, tot_presento, tot_selecc)
    output_suayed["overall"][str(year)] = entry

# ---- Per carrera / per plantel ----
for lic in sorted(suayed_all_licenciaturas):
    pkeys = sorted(suayed_lic_planteles[lic], key=lambda k: suayed_plantel_display.get(k, k))
    plantel_names = {pkey: suayed_plantel_display.get(pkey, pkey) for pkey in pkeys}

    by_plantel = {}

    # "TODOS" planteles combinados para esta carrera
    todos_by_year = {}
    for year in YEARS:
        vals = []
        tot_aspirantes = tot_presento = tot_selecc = 0
        for pkey in pkeys:
            vlist = suayed_values[year].get(lic, {}).get(pkey, [])
            vals.extend(vlist)
            tot_presento += len(vlist)
            tot_aspirantes += suayed_aspirantes[year].get(lic, {}).get(pkey, 0)
            tot_selecc += suayed_seleccionados[year].get(lic, {}).get(pkey, 0)
        entry = stats_from_values(vals) or {}
        entry["totals"] = make_totals(tot_aspirantes, tot_presento, tot_selecc)
        todos_by_year[str(year)] = entry
    by_plantel[ALL_PLANTEL_KEY] = todos_by_year

    # Cada plantel individual
    for pkey in pkeys:
        pyear = {}
        for year in YEARS:
            vlist = suayed_values[year].get(lic, {}).get(pkey, [])
            entry = stats_from_values(vlist) or {}
            aspirantes = suayed_aspirantes[year].get(lic, {}).get(pkey, 0)
            selecc = suayed_seleccionados[year].get(lic, {}).get(pkey, 0)
            entry["totals"] = make_totals(aspirantes, len(vlist), selecc)
            pyear[str(year)] = entry
        by_plantel[pkey] = pyear

    output_suayed["carreras"][lic] = {
        "planteles": [{"key": ALL_PLANTEL_KEY, "name": "Todos los planteles"}]
        + [{"key": pkey, "name": plantel_names[pkey]} for pkey in pkeys],
        "byPlantel": by_plantel,
    }

# ---- Ranking de cambio de distribucion 2025 -> 2026 (Wasserstein-1) ----
suayed_wasserstein_rows = []
for lic in sorted(suayed_all_licenciaturas):
    for pkey in suayed_lic_planteles[lic]:
        vals_a = suayed_values[YEAR_A].get(lic, {}).get(pkey, [])
        vals_b = suayed_values[YEAR_B].get(lic, {}).get(pkey, [])
        if len(vals_a) < MIN_N_WASSERSTEIN or len(vals_b) < MIN_N_WASSERSTEIN:
            continue
        dist = wasserstein1_int(vals_a, vals_b)
        if dist is None:
            continue
        stats_a = stats_from_values(vals_a)
        stats_b = stats_from_values(vals_b)
        suayed_wasserstein_rows.append({
            "licenciatura": lic,
            "plantel": suayed_plantel_display.get(pkey, pkey),
            "distance": round(dist, 2),
            "n2025": stats_a["n"],
            "n2026": stats_b["n"],
            "medianDiff": round(stats_b["median"] - stats_a["median"], 1),
            "meanDiff": round(stats_b["mean"] - stats_a["mean"], 2),
        })

suayed_wasserstein_rows.sort(key=lambda r: r["distance"], reverse=True)
output_suayed["wasserstein2025_2026"] = {
    "minN": MIN_N_WASSERSTEIN,
    "yearA": YEAR_A,
    "yearB": YEAR_B,
    "top": suayed_wasserstein_rows,
}
print(f"Wasserstein SUAYED: {len(suayed_wasserstein_rows)} combinaciones comparables (n>={MIN_N_WASSERSTEIN} en ambos anios)")

payload_suayed = json.dumps(output_suayed, ensure_ascii=False, separators=(",", ":"))
SUAYED_JSON_OUT.write_text(payload_suayed)
print(f"Escrito {SUAYED_JSON_OUT} ({SUAYED_JSON_OUT.stat().st_size / 1e6:.2f} MB)")

SUAYED_JS_OUT.write_text("const UNAM_DATA_SUAYED = " + payload_suayed + ";\n")
print(f"Escrito {SUAYED_JS_OUT} ({SUAYED_JS_OUT.stat().st_size / 1e6:.2f} MB)")


# =====================================================================
# SUAYED — Noviembre (convocatoria extraordinaria de noviembre, modalidad
# a distancia). Misma idea que el bloque SUAYED de arriba (solo hay
# resultados individuales, no resumen por licenciatura/plantel), pero
# esta convocatoria no necesariamente tiene datos para todos los años de
# YEARS (2021-2026): a la fecha en que se escribió este script solo había
# datos 2021-2024. Por eso "meta.years" y el par de años usado para el
# ranking de Wasserstein se calculan dinámicamente a partir de lo que de
# verdad aparece en el CSV, en vez de asumir 2025/2026 como en los otros
# dos datasets.
# =====================================================================
print("\n=== SUAYED — Noviembre ===")
SUAYED_NOV_DIR = BASE / "Suayed" / "noviembre"
SUAYED_NOV_JSON_OUT = Path(__file__).parent / "data_suayed_noviembre.json"
SUAYED_NOV_JS_OUT = Path(__file__).parent / "data_suayed_noviembre.js"

suayed_nov_values = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
suayed_nov_aspirantes = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
suayed_nov_seleccionados = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
suayed_nov_plantel_display = {}
suayed_nov_years_present = set()

suayed_nov_files = sorted(SUAYED_NOV_DIR.glob("resultados_individuales_unam_suayed_noviembre_*.csv"))
print(f"Leyendo archivos SUAYED Noviembre: {[f.name for f in suayed_nov_files]}")
for fp in suayed_nov_files:
    with fp.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["anio"])
            suayed_nov_years_present.add(year)
            lic = row["licenciatura"].strip()
            plantel_raw = row["plantel"].strip()
            pkey = norm_key(plantel_raw)
            if pkey not in suayed_nov_plantel_display or (
                any(ord(c) > 127 for c in plantel_raw)
                and not any(ord(c) > 127 for c in suayed_nov_plantel_display[pkey])
            ):
                suayed_nov_plantel_display[pkey] = plantel_raw

            suayed_nov_aspirantes[year][lic][pkey] += 1
            if row["acreditado"].strip() == "S":
                suayed_nov_seleccionados[year][lic][pkey] += 1

            a = row["aciertos"].strip()
            if a:
                try:
                    suayed_nov_values[year][lic][pkey].append(int(a))
                except ValueError:
                    pass

NOV_YEARS = sorted(suayed_nov_years_present)
print(f"Años con datos SUAYED Noviembre: {NOV_YEARS}")

print("Calculando licenciaturas y planteles SUAYED Noviembre...")
suayed_nov_all_licenciaturas = set()
suayed_nov_lic_planteles = defaultdict(set)
for year in NOV_YEARS:
    for lic, pmap in suayed_nov_aspirantes[year].items():
        suayed_nov_all_licenciaturas.add(lic)
        for pkey in pmap:
            suayed_nov_lic_planteles[lic].add(pkey)

print(f"Total licenciaturas SUAYED Noviembre: {len(suayed_nov_all_licenciaturas)}")

output_suayed_nov = {
    "meta": {
        "years": NOV_YEARS,
        "binEdges": BIN_EDGES,
        "generatedNote": "UNAM resultados individuales SUAYED convocatoria Noviembre (oferta y aciertos minimos no disponibles)",
    },
    "overall": {},
    "carreras": {},
}

# ---- Overall (todas las carreras, todos los planteles) ----
for year in NOV_YEARS:
    all_vals = []
    tot_aspirantes = tot_presento = tot_selecc = 0
    for lic, pmap in suayed_nov_aspirantes[year].items():
        for pkey, cnt in pmap.items():
            tot_aspirantes += cnt
    for lic, pmap in suayed_nov_values[year].items():
        for pkey, vlist in pmap.items():
            all_vals.extend(vlist)
            tot_presento += len(vlist)
    for lic, pmap in suayed_nov_seleccionados[year].items():
        for pkey, cnt in pmap.items():
            tot_selecc += cnt

    entry = stats_from_values(all_vals) or {}
    entry["totals"] = make_totals(tot_aspirantes, tot_presento, tot_selecc)
    output_suayed_nov["overall"][str(year)] = entry

# ---- Per carrera / per plantel ----
for lic in sorted(suayed_nov_all_licenciaturas):
    pkeys = sorted(suayed_nov_lic_planteles[lic], key=lambda k: suayed_nov_plantel_display.get(k, k))
    plantel_names = {pkey: suayed_nov_plantel_display.get(pkey, pkey) for pkey in pkeys}

    by_plantel = {}

    todos_by_year = {}
    for year in NOV_YEARS:
        vals = []
        tot_aspirantes = tot_presento = tot_selecc = 0
        for pkey in pkeys:
            vlist = suayed_nov_values[year].get(lic, {}).get(pkey, [])
            vals.extend(vlist)
            tot_presento += len(vlist)
            tot_aspirantes += suayed_nov_aspirantes[year].get(lic, {}).get(pkey, 0)
            tot_selecc += suayed_nov_seleccionados[year].get(lic, {}).get(pkey, 0)
        entry = stats_from_values(vals) or {}
        entry["totals"] = make_totals(tot_aspirantes, tot_presento, tot_selecc)
        todos_by_year[str(year)] = entry
    by_plantel[ALL_PLANTEL_KEY] = todos_by_year

    for pkey in pkeys:
        pyear = {}
        for year in NOV_YEARS:
            vlist = suayed_nov_values[year].get(lic, {}).get(pkey, [])
            entry = stats_from_values(vlist) or {}
            aspirantes = suayed_nov_aspirantes[year].get(lic, {}).get(pkey, 0)
            selecc = suayed_nov_seleccionados[year].get(lic, {}).get(pkey, 0)
            entry["totals"] = make_totals(aspirantes, len(vlist), selecc)
            pyear[str(year)] = entry
        by_plantel[pkey] = pyear

    output_suayed_nov["carreras"][lic] = {
        "planteles": [{"key": ALL_PLANTEL_KEY, "name": "Todos los planteles"}]
        + [{"key": pkey, "name": plantel_names[pkey]} for pkey in pkeys],
        "byPlantel": by_plantel,
    }

# ---- Ranking de cambio de distribucion entre los 2 anios mas recientes con datos ----
if len(NOV_YEARS) >= 2:
    NOV_YEAR_A, NOV_YEAR_B = NOV_YEARS[-2], NOV_YEARS[-1]
    suayed_nov_wasserstein_rows = []
    for lic in sorted(suayed_nov_all_licenciaturas):
        for pkey in suayed_nov_lic_planteles[lic]:
            vals_a = suayed_nov_values[NOV_YEAR_A].get(lic, {}).get(pkey, [])
            vals_b = suayed_nov_values[NOV_YEAR_B].get(lic, {}).get(pkey, [])
            if len(vals_a) < MIN_N_WASSERSTEIN or len(vals_b) < MIN_N_WASSERSTEIN:
                continue
            dist = wasserstein1_int(vals_a, vals_b)
            if dist is None:
                continue
            stats_a = stats_from_values(vals_a)
            stats_b = stats_from_values(vals_b)
            suayed_nov_wasserstein_rows.append({
                "licenciatura": lic,
                "plantel": suayed_nov_plantel_display.get(pkey, pkey),
                "distance": round(dist, 2),
                "n2025": stats_a["n"],
                "n2026": stats_b["n"],
                "medianDiff": round(stats_b["median"] - stats_a["median"], 1),
                "meanDiff": round(stats_b["mean"] - stats_a["mean"], 2),
            })
    suayed_nov_wasserstein_rows.sort(key=lambda r: r["distance"], reverse=True)
else:
    NOV_YEAR_A = NOV_YEAR_B = None
    suayed_nov_wasserstein_rows = []

output_suayed_nov["wasserstein2025_2026"] = {
    "minN": MIN_N_WASSERSTEIN,
    "yearA": NOV_YEAR_A,
    "yearB": NOV_YEAR_B,
    "top": suayed_nov_wasserstein_rows,
}
print(f"Wasserstein SUAYED Noviembre ({NOV_YEAR_A}->{NOV_YEAR_B}): {len(suayed_nov_wasserstein_rows)} combinaciones comparables (n>={MIN_N_WASSERSTEIN} en ambos anios)")

payload_suayed_nov = json.dumps(output_suayed_nov, ensure_ascii=False, separators=(",", ":"))
SUAYED_NOV_JSON_OUT.write_text(payload_suayed_nov)
print(f"Escrito {SUAYED_NOV_JSON_OUT} ({SUAYED_NOV_JSON_OUT.stat().st_size / 1e6:.2f} MB)")

SUAYED_NOV_JS_OUT.write_text("const UNAM_DATA_SUAYED_NOVIEMBRE = " + payload_suayed_nov + ";\n")
print(f"Escrito {SUAYED_NOV_JS_OUT} ({SUAYED_NOV_JS_OUT.stat().st_size / 1e6:.2f} MB)")
