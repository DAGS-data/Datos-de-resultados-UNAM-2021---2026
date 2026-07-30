(function () {
  "use strict";

  // Permite reusar este mismo app.js en varias páginas (Licenciatura,
  // SUAYED, ...). Cada página define window.ACTIVE_DATA con su propio
  // dataset (ej. UNAM_DATA_SUAYED) antes de cargar app.js; si no lo hace,
  // se usa UNAM_DATA (dataset por defecto de index.html) para no romper
  // el comportamiento existente.
  const DATA = window.ACTIVE_DATA || (typeof UNAM_DATA !== "undefined" ? UNAM_DATA : undefined);

  const YEARS = DATA.meta.years;
  const BIN_EDGES = DATA.meta.binEdges;
  const ALL_KEY = "__ALL__";
  const YEAR_ALL = "ALL";

  const nfInt = new Intl.NumberFormat("es-MX");
  const nf1 = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  const LOWER_WORDS = new Set(["de", "del", "la", "las", "el", "los", "y", "en", "a", "al", "e"]);
  function titleCase(str) {
    return str
      .toLowerCase()
      .split(" ")
      .map((w, i) => (i > 0 && LOWER_WORDS.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
      .join(" ");
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function hexToRgba(hex, alpha) {
    const h = hex.replace("#", "");
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function seriesColor(year) {
    const slot = year - 2020; // 2021 -> 1 ... 2026 -> 6
    return cssVar(`--series-${slot}`);
  }

  function binLabels() {
    const labels = [];
    for (let i = 0; i < BIN_EDGES.length - 1; i++) {
      const lo = BIN_EDGES[i];
      const hi = i === BIN_EDGES.length - 2 ? BIN_EDGES[i + 1] : BIN_EDGES[i + 1] - 1;
      labels.push(`${lo}-${hi}`);
    }
    return labels;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function pct(n, d) {
    if (!d) return null;
    return (n / d) * 100;
  }

  // ---------- DOM refs ----------
  const carreraSelect = document.getElementById("carrera-select");
  const plantelSelect = document.getElementById("plantel-select");
  const anioSelect = document.getElementById("anio-select");
  const resetBtn = document.getElementById("reset-filters");
  const scopeBanner = document.getElementById("scope-banner");
  const kpiRow = document.getElementById("kpi-row");

  // ---------- Populate selects ----------
  const carreraKeys = Object.keys(DATA.carreras).sort((a, b) =>
    titleCase(a).localeCompare(titleCase(b), "es")
  );
  carreraSelect.innerHTML =
    `<option value="${ALL_KEY}">Todas las carreras</option>` +
    carreraKeys.map((k) => `<option value="${escapeHtml(k)}">${escapeHtml(titleCase(k))}</option>`).join("");

  anioSelect.innerHTML =
    `<option value="${YEAR_ALL}">Todos los años</option>` +
    YEARS.map((y) => `<option value="${y}">${y}</option>`).join("");

  function populatePlanteles() {
    const lic = carreraSelect.value;
    if (lic === ALL_KEY) {
      plantelSelect.innerHTML = `<option value="__TODOS__">Todos los planteles</option>`;
      plantelSelect.disabled = true;
      return;
    }
    plantelSelect.disabled = false;
    const planteles = DATA.carreras[lic].planteles;
    plantelSelect.innerHTML = planteles
      .map((p) => `<option value="${escapeHtml(p.key)}">${escapeHtml(titleCase(p.name))}</option>`)
      .join("");
  }

  function getCurrentData() {
    const lic = carreraSelect.value;
    if (lic === ALL_KEY) return DATA.overall;
    const pkey = plantelSelect.value;
    return DATA.carreras[lic].byPlantel[pkey];
  }

  function getSelectedYear() {
    return anioSelect.value === YEAR_ALL ? null : Number(anioSelect.value);
  }

  function activeYears(data) {
    return YEARS.filter((y) => data[String(y)] && data[String(y)].n);
  }

  // Años a usar en las secciones que sí respetan el filtro de Año
  // (distribución de aciertos, KPIs). null = mostrar todos.
  function scopedYears(data, selectedYear) {
    const active = activeYears(data);
    return selectedYear == null ? active : active.filter((y) => y === selectedYear);
  }

  // ---------- Chart instances ----------
  let charts = {};
  function destroyCharts() {
    Object.values(charts).forEach((c) => c && c.destroy());
    charts = {};
  }

  function baseFontColor() {
    return cssVar("--text-secondary");
  }
  function gridColor() {
    return cssVar("--gridline");
  }

  function renderAll() {
    const data = getCurrentData();
    const selectedYear = getSelectedYear();
    const years = scopedYears(data, selectedYear);

    renderScopeBanner(selectedYear);
    renderKpis(data, years);
    renderHistogram(data, years, selectedYear);
    renderBoxplot(data, years, selectedYear);
    renderStatsTable(data, years);
    renderWassersteinTable();
    renderDistanceScatter();
    renderLowScoreTable(selectedYear);
  }

  function renderScopeBanner(selectedYear) {
    const lic = carreraSelect.value;
    const parts = [];
    if (lic === ALL_KEY) {
      parts.push("<strong>Todas las carreras</strong>", "<strong>Todos los planteles</strong>");
    } else {
      const pname = plantelSelect.options[plantelSelect.selectedIndex]
        ? plantelSelect.options[plantelSelect.selectedIndex].text
        : "";
      parts.push(`<strong>${escapeHtml(titleCase(lic))}</strong>`, `<strong>${escapeHtml(pname)}</strong>`);
    }
    parts.push(`<strong>${selectedYear == null ? "Todos los años" : selectedYear}</strong>`);
    scopeBanner.innerHTML = "Mostrando: " + parts.join(" · ");
  }

  function renderKpis(data, years) {
    if (years.length === 0) {
      kpiRow.innerHTML = `<div class="kpi-tile"><div class="kpi-label">Sin datos para este filtro</div></div>`;
      return;
    }
    const last = years[years.length - 1];
    const prevCandidate = last - 1;
    const prevEntry = data[prevCandidate] && data[prevCandidate].n ? data[prevCandidate] : null;
    const prev = prevEntry ? prevCandidate : null;
    const cur = data[last];

    const tiles = [];

    const aspirantes = cur.totals.aspirantes;
    const aspirantesPrev = prevEntry ? prevEntry.totals.aspirantes : null;
    tiles.push(kpiTile(`Aspirantes ${last}`, nfInt.format(aspirantes), deltaText(aspirantes, aspirantesPrev, prev)));

    const aceptados = cur.totals.seleccionados;
    const aceptadosPrev = prevEntry ? prevEntry.totals.seleccionados : null;
    tiles.push(kpiTile(`Aceptados ${last}`, nfInt.format(aceptados), deltaText(aceptados, aceptadosPrev, prev)));

    const tasa = pct(cur.totals.seleccionados, cur.totals.presentaronExamen);
    const tasaPrev = prevEntry ? pct(prevEntry.totals.seleccionados, prevEntry.totals.presentaronExamen) : null;
    tiles.push(
      kpiTile(
        `Aceptados / presentaron ${last}`,
        tasa != null ? tasa.toFixed(1) + "%" : "—",
        tasa != null && tasaPrev != null
          ? `${tasa - tasaPrev >= 0 ? "+" : ""}${(tasa - tasaPrev).toFixed(1)} pp vs ${prev}`
          : ""
      )
    );

    const mediana = cur.median;
    const medianaPrev = prevEntry ? prevEntry.median : null;
    tiles.push(
      kpiTile(
        `Mediana de aciertos ${last}`,
        mediana != null ? nf1.format(mediana) : "—",
        mediana != null && medianaPrev != null
          ? `${mediana - medianaPrev >= 0 ? "+" : ""}${nf1.format(mediana - medianaPrev)} vs ${prev}`
          : ""
      )
    );

    kpiRow.innerHTML = tiles.join("");
  }

  function deltaText(cur, prev, prevYear) {
    if (cur == null || prev == null || !prevYear) return "";
    const diff = cur - prev;
    const sign = diff >= 0 ? "+" : "";
    const relPct = prev !== 0 ? (diff / prev) * 100 : 0;
    return `${sign}${nfInt.format(diff)} (${sign}${relPct.toFixed(1)}%) vs ${prevYear}`;
  }

  function kpiTile(label, value, delta) {
    return `<div class="kpi-tile">
      <div class="kpi-label">${escapeHtml(label)}</div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-delta">${delta ? escapeHtml(delta) : "&nbsp;"}</div>
    </div>`;
  }

  function renderHistogram(data, years, selectedYear) {
    document.getElementById("histogram-title").textContent =
      selectedYear == null ? "Histograma superpuesto por año" : `Histograma — ${selectedYear}`;
    const ctx = document.getElementById("chart-histogram").getContext("2d");
    const datasets = years.map((y) => ({
      label: String(y),
      data: data[y].histogram,
      backgroundColor: hexToRgba(seriesColor(y), 0.42),
      borderColor: seriesColor(y),
      borderWidth: 1,
      grouped: false,
      barPercentage: 1.0,
      categoryPercentage: 1.0,
    }));
    charts.histogram = new Chart(ctx, {
      type: "bar",
      data: { labels: binLabels(), datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            title: { display: true, text: "Aciertos", color: baseFontColor() },
            grid: { display: false },
            ticks: { color: cssVar("--text-muted"), maxRotation: 0, autoSkip: true, autoSkipPadding: 8 },
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: "Aspirantes", color: baseFontColor() },
            grid: { color: gridColor() },
            ticks: { color: cssVar("--text-muted") },
          },
        },
        plugins: {
          legend: { display: years.length > 1, position: "bottom", labels: { color: baseFontColor(), boxWidth: 12, boxHeight: 12 } },
          tooltip: { callbacks: { title: (items) => `Aciertos ${items[0].label}` } },
        },
      },
    });
  }

  function renderBoxplot(data, years, selectedYear) {
    document.getElementById("boxplot-title").textContent =
      selectedYear == null ? "Caja y bigotes por año" : `Caja y bigotes — ${selectedYear}`;
    const ctx = document.getElementById("chart-boxplot").getContext("2d");
    const items = years.map((y) => {
      const e = data[y];
      return {
        min: e.min,
        q1: e.q1,
        median: e.median,
        q3: e.q3,
        max: e.max,
        whiskerMin: e.whiskerMin,
        whiskerMax: e.whiskerMax,
        outliers: [],
        items: [],
        mean: e.mean,
      };
    });
    charts.boxplot = new Chart(ctx, {
      type: "boxplot",
      data: {
        labels: years.map(String),
        datasets: [
          {
            label: "Aciertos",
            data: items,
            backgroundColor: years.map((y) => hexToRgba(seriesColor(y), 0.32)),
            borderColor: years.map((y) => seriesColor(y)),
            borderWidth: 2,
            itemRadius: 0,
            medianColor: years.map((y) => seriesColor(y)),
            outlierColor: years.map((y) => seriesColor(y)),
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--text-muted") } },
          y: {
            min: 0,
            max: 120,
            title: { display: true, text: "Aciertos", color: baseFontColor() },
            grid: { color: gridColor() },
            ticks: { color: cssVar("--text-muted") },
          },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  function renderStatsTable(data, years) {
    const tbody = document.querySelector("#stats-table tbody");
    tbody.innerHTML = years
      .map((y) => {
        const e = data[y];
        return `<tr>
        <td><span class="year-swatch" style="background:${seriesColor(y)}"></span>${y}</td>
        <td>${nfInt.format(e.n)}</td>
        <td>${nf1.format(e.mean)}</td>
        <td>${nf1.format(e.median)}</td>
        <td>${nf1.format(e.std)}</td>
        <td>${nfInt.format(e.min)}</td>
        <td>${nf1.format(e.q1)}</td>
        <td>${nf1.format(e.q3)}</td>
        <td>${nfInt.format(e.max)}</td>
      </tr>`;
      })
      .join("");
  }

  function renderDistanceScatter() {
    const w = DATA.wasserstein2025_2026;
    const yearA = w && w.yearA != null ? w.yearA : 2025;
    const yearB = w && w.yearB != null ? w.yearB : 2026;
    const ctx = document.getElementById("chart-scatter-distance").getContext("2d");
    const color = cssVar("--series-5");
    const points = (w && w.top ? w.top : []).map((r) => ({
      x: r.medianDiff,
      y: r.n2026,
      label: `${titleCase(r.licenciatura)} · ${titleCase(r.plantel)}`,
    }));
    charts.scatterDistance = new Chart(ctx, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Carrera-plantel",
            data: points,
            backgroundColor: hexToRgba(color, 0.45),
            borderColor: color,
            borderWidth: 1,
            radius: 5,
            hoverRadius: 7,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scales: {
          x: {
            title: { display: true, text: `Cambio en mediana de aciertos (${yearB} − ${yearA})`, color: baseFontColor() },
            grid: { color: gridColor() },
            ticks: { color: cssVar("--text-muted") },
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: `Realizaron examen ${yearB}`, color: baseFontColor() },
            grid: { color: gridColor() },
            ticks: { color: cssVar("--text-muted") },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => items[0].raw.label,
              label: (item) => [`Realizaron examen ${yearB}: ${nfInt.format(item.raw.y)}`, `Cambio mediana: ${item.raw.x >= 0 ? "+" : ""}${nf1.format(item.raw.x)}`],
            },
          },
        },
      },
    });
  }

  function renderWassersteinTable() {
    const w = DATA.wasserstein2025_2026;
    const note = document.getElementById("wasserstein-note");
    const tbody = document.querySelector("#wasserstein-table tbody");
    if (!w || !w.top || w.top.length === 0) {
      note.textContent = "Sin datos suficientes.";
      tbody.innerHTML = "";
      return;
    }
    const yearA = w.yearA != null ? w.yearA : 2025;
    const yearB = w.yearB != null ? w.yearB : 2026;
    note.textContent = `${w.top.length} combinaciones comparables · al menos ${w.minN} aspirantes con aciertos en ${yearA} y en ${yearB}`;
    tbody.innerHTML = w.top
      .map((r, i) => {
        const sign = r.medianDiff >= 0 ? "+" : "";
        return `<tr>
        <td>${i + 1}</td>
        <td>${escapeHtml(titleCase(r.licenciatura))}</td>
        <td>${escapeHtml(titleCase(r.plantel))}</td>
        <td>${nf1.format(r.distance)}</td>
        <td>${sign}${nf1.format(r.medianDiff)}</td>
        <td>${nfInt.format(r.n2025)}</td>
        <td>${nfInt.format(r.n2026)}</td>
      </tr>`;
      })
      .join("");
  }

  // ---------- Carreras-plantel con aciertos < 5 (independiente de Carrera/Plantel, depende de Año) ----------
  function buildLowScoreRows(selectedYear) {
    const rows = [];
    Object.keys(DATA.carreras).forEach((lic) => {
      const info = DATA.carreras[lic];
      info.planteles.forEach((p) => {
        if (p.key === "__TODOS__") return;
        const byYear = info.byPlantel[p.key];
        if (selectedYear != null) {
          const e = byYear[String(selectedYear)];
          if (!e || !e.n) return;
          rows.push({ lic, plantel: p.name, nLt5: e.nLt5, n: e.n });
        } else {
          const perYear = {};
          let total = 0;
          let anyData = false;
          YEARS.forEach((y) => {
            const e = byYear[String(y)];
            const v = e && e.n ? e.nLt5 : null;
            perYear[y] = v;
            if (v != null) {
              total += v;
              anyData = true;
            }
          });
          if (!anyData) return;
          rows.push({ lic, plantel: p.name, perYear, total });
        }
      });
    });
    return rows;
  }

  function renderLowScoreTable(selectedYear) {
    const rows = buildLowScoreRows(selectedYear);
    const thead = document.querySelector("#lowscore-table thead");
    const tbody = document.querySelector("#lowscore-table tbody");
    const note = document.getElementById("lowscore-note");

    if (rows.length === 0) {
      thead.innerHTML = "";
      tbody.innerHTML = "";
      note.textContent = "Sin datos suficientes.";
      return;
    }

    if (selectedYear != null) {
      rows.sort((a, b) => b.nLt5 - a.nLt5);
      const top = rows.slice(0, 15);
      note.textContent = `Año ${selectedYear} · top 15 combinaciones carrera-plantel`;
      thead.innerHTML = `<tr><th>#</th><th>Carrera</th><th>Plantel</th><th>Aciertos &lt; 5</th><th>% de n</th><th>n ${selectedYear}</th></tr>`;
      tbody.innerHTML = top
        .map((r, i) => {
          const p = r.n ? (r.nLt5 / r.n) * 100 : 0;
          return `<tr>
          <td>${i + 1}</td>
          <td>${escapeHtml(titleCase(r.lic))}</td>
          <td>${escapeHtml(titleCase(r.plantel))}</td>
          <td>${nfInt.format(r.nLt5)}</td>
          <td>${p.toFixed(1)}%</td>
          <td>${nfInt.format(r.n)}</td>
        </tr>`;
        })
        .join("");
    } else {
      rows.sort((a, b) => b.total - a.total);
      const top = rows.slice(0, 15);
      note.textContent = "Todos los años · ranking por total acumulado 2021–2026 · top 15";
      const yearHeaders = YEARS.map((y) => `<th>${y}</th>`).join("");
      thead.innerHTML = `<tr><th>#</th><th>Carrera</th><th>Plantel</th>${yearHeaders}<th>Total</th></tr>`;
      tbody.innerHTML = top
        .map((r, i) => {
          const cells = YEARS.map((y) => `<td>${r.perYear[y] != null ? nfInt.format(r.perYear[y]) : "—"}</td>`).join("");
          return `<tr>
          <td>${i + 1}</td>
          <td>${escapeHtml(titleCase(r.lic))}</td>
          <td>${escapeHtml(titleCase(r.plantel))}</td>
          ${cells}
          <td>${nfInt.format(r.total)}</td>
        </tr>`;
        })
        .join("");
    }
  }

  function fullRender() {
    destroyCharts();
    renderAll();
  }

  carreraSelect.addEventListener("change", () => {
    populatePlanteles();
    fullRender();
  });
  plantelSelect.addEventListener("change", fullRender);
  anioSelect.addEventListener("change", fullRender);
  resetBtn.addEventListener("click", () => {
    carreraSelect.value = ALL_KEY;
    anioSelect.value = YEAR_ALL;
    populatePlanteles();
    fullRender();
  });

  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fullRender);
  }

  populatePlanteles();
  fullRender();
})();
