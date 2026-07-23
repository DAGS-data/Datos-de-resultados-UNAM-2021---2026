(function () {
  "use strict";

  const YEARS = UNAM_DATA.meta.years;
  const BIN_EDGES = UNAM_DATA.meta.binEdges;
  const ALL_KEY = "__ALL__";

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

  // ---------- DOM refs ----------
  const carreraSelect = document.getElementById("carrera-select");
  const plantelSelect = document.getElementById("plantel-select");
  const resetBtn = document.getElementById("reset-filters");
  const scopeBanner = document.getElementById("scope-banner");
  const kpiRow = document.getElementById("kpi-row");

  // ---------- Populate carrera select ----------
  const carreraKeys = Object.keys(UNAM_DATA.carreras).sort((a, b) =>
    titleCase(a).localeCompare(titleCase(b), "es")
  );
  carreraSelect.innerHTML =
    `<option value="${ALL_KEY}">Todas las carreras</option>` +
    carreraKeys.map((k) => `<option value="${escapeHtml(k)}">${escapeHtml(titleCase(k))}</option>`).join("");

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function populatePlanteles() {
    const lic = carreraSelect.value;
    if (lic === ALL_KEY) {
      plantelSelect.innerHTML = `<option value="__TODOS__">Todos los planteles</option>`;
      plantelSelect.disabled = true;
      return;
    }
    plantelSelect.disabled = false;
    const planteles = UNAM_DATA.carreras[lic].planteles;
    plantelSelect.innerHTML = planteles
      .map((p) => `<option value="${escapeHtml(p.key)}">${escapeHtml(titleCase(p.name))}</option>`)
      .join("");
  }

  function getCurrentData() {
    const lic = carreraSelect.value;
    if (lic === ALL_KEY) return UNAM_DATA.overall;
    const pkey = plantelSelect.value;
    return UNAM_DATA.carreras[lic].byPlantel[pkey];
  }

  function activeYears(data) {
    return YEARS.filter((y) => data[String(y)] && data[String(y)].n);
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
    const years = activeYears(data);
    renderScopeBanner();
    renderKpis(data, years);
    renderHistogram(data, years);
    renderBoxplot(data, years);
    renderStatsTable(data, years);
    renderMedianChart(data, years);
    renderCountBar("chart-aspirantes", data, years, (y) => data[y].totals.aspirantes, "Aspirantes");
    renderCountBar("chart-lugares", data, years, (y) => data[y].totals.oferta, "Lugares");
    renderCountBar("chart-aceptados", data, years, (y) => data[y].totals.seleccionados, "Aceptados");
    renderRateChart("chart-rate-aspirantes", data, years, (y) => pct(data[y].totals.seleccionados, data[y].totals.aspirantes), "Aceptados / Aspirantes", "--series-1");
    renderRateChart("chart-rate-lugares", data, years, (y) => pct(data[y].totals.seleccionados, data[y].totals.oferta), "Aceptados / Lugares", "--series-5");
    renderTotalsTable(data, years);
  }

  function renderScopeBanner() {
    const lic = carreraSelect.value;
    if (lic === ALL_KEY) {
      scopeBanner.innerHTML = `Mostrando: <strong>Todas las carreras</strong> · <strong>Todos los planteles</strong>`;
    } else {
      const pname = plantelSelect.options[plantelSelect.selectedIndex]
        ? plantelSelect.options[plantelSelect.selectedIndex].text
        : "";
      scopeBanner.innerHTML = `Mostrando: <strong>${escapeHtml(titleCase(lic))}</strong> · <strong>${escapeHtml(pname)}</strong>`;
    }
  }

  function pct(n, d) {
    if (!d) return null;
    return (n / d) * 100;
  }

  function renderKpis(data, years) {
    if (years.length === 0) {
      kpiRow.innerHTML = `<div class="kpi-tile"><div class="kpi-label">Sin datos</div></div>`;
      return;
    }
    const last = years[years.length - 1];
    const prev = years.length > 1 ? years[years.length - 2] : null;
    const cur = data[last];
    const prevEntry = prev ? data[prev] : null;

    const tiles = [];

    const aspirantes = cur.totals.aspirantes;
    const aspirantesPrev = prevEntry ? prevEntry.totals.aspirantes : null;
    tiles.push(
      kpiTile(
        `Aspirantes ${last}`,
        nfInt.format(aspirantes),
        deltaText(aspirantes, aspirantesPrev, prev)
      )
    );

    const aceptados = cur.totals.seleccionados;
    const aceptadosPrev = prevEntry ? prevEntry.totals.seleccionados : null;
    tiles.push(
      kpiTile(
        `Aceptados ${last}`,
        nfInt.format(aceptados),
        deltaText(aceptados, aceptadosPrev, prev)
      )
    );

    const tasa = pct(cur.totals.seleccionados, cur.totals.aspirantes);
    const tasaPrev = prevEntry ? pct(prevEntry.totals.seleccionados, prevEntry.totals.aspirantes) : null;
    tiles.push(
      kpiTile(
        `Tasa de aceptación ${last}`,
        tasa != null ? tasa.toFixed(1) + "%" : "—",
        tasa != null && tasaPrev != null
          ? `${(tasa - tasaPrev >= 0 ? "+" : "")}${(tasa - tasaPrev).toFixed(1)} pp vs ${prev}`
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
          ? `${(mediana - medianaPrev >= 0 ? "+" : "")}${nf1.format(mediana - medianaPrev)} vs ${prev}`
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

  function renderHistogram(data, years) {
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
          legend: { position: "bottom", labels: { color: baseFontColor(), boxWidth: 12, boxHeight: 12 } },
          tooltip: { callbacks: { title: (items) => `Aciertos ${items[0].label}` } },
        },
      },
    });
  }

  function renderBoxplot(data, years) {
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

  function renderMedianChart(data, years) {
    const ctx = document.getElementById("chart-median").getContext("2d");
    const hasMinimos = years.some((y) => data[y].totals.aciertosMinimosAvg != null);
    const datasets = [
      {
        label: "Mediana de aciertos",
        data: years.map((y) => data[y].median),
        borderColor: cssVar("--series-1"),
        backgroundColor: hexToRgba(cssVar("--series-1"), 0.12),
        pointBackgroundColor: cssVar("--series-1"),
        pointBorderColor: cssVar("--surface-1"),
        pointBorderWidth: 2,
        pointRadius: 5,
        tension: 0.25,
        fill: false,
      },
    ];
    if (hasMinimos) {
      datasets.push({
        label: "Aciertos mínimos (promedio)",
        data: years.map((y) => data[y].totals.aciertosMinimosAvg),
        borderColor: cssVar("--series-6"),
        backgroundColor: hexToRgba(cssVar("--series-6"), 0.12),
        pointBackgroundColor: cssVar("--series-6"),
        pointBorderColor: cssVar("--surface-1"),
        pointBorderWidth: 2,
        pointRadius: 5,
        borderDash: [6, 4],
        tension: 0.25,
        fill: false,
      });
    }
    charts.median = new Chart(ctx, {
      type: "line",
      data: { labels: years.map(String), datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
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
        plugins: {
          legend: { position: "bottom", labels: { color: baseFontColor(), boxWidth: 12, boxHeight: 12 } },
        },
      },
    });
  }

  function renderCountBar(canvasId, data, years, accessor, label) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    charts[canvasId] = new Chart(ctx, {
      type: "bar",
      data: {
        labels: years.map(String),
        datasets: [
          {
            label,
            data: years.map((y) => accessor(y) || 0),
            backgroundColor: years.map((y) => hexToRgba(seriesColor(y), 0.55)),
            borderColor: years.map((y) => seriesColor(y)),
            borderWidth: 1,
            borderRadius: 4,
            maxBarThickness: 40,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--text-muted") } },
          y: {
            beginAtZero: true,
            grid: { color: gridColor() },
            ticks: { color: cssVar("--text-muted") },
          },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  function renderRateChart(canvasId, data, years, accessor, label, colorVar) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    const color = cssVar(colorVar);
    charts[canvasId] = new Chart(ctx, {
      type: "line",
      data: {
        labels: years.map(String),
        datasets: [
          {
            label,
            data: years.map((y) => accessor(y)),
            borderColor: color,
            backgroundColor: hexToRgba(color, 0.12),
            pointBackgroundColor: years.map((y) => seriesColor(y)),
            pointBorderColor: cssVar("--surface-1"),
            pointBorderWidth: 2,
            pointRadius: 5,
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--text-muted") } },
          y: {
            beginAtZero: true,
            title: { display: true, text: "%", color: baseFontColor() },
            grid: { color: gridColor() },
            ticks: { color: cssVar("--text-muted"), callback: (v) => v + "%" },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (item) => `${item.dataset.label}: ${item.formattedValue}%` } },
        },
      },
    });
  }

  function renderTotalsTable(data, years) {
    const tbody = document.querySelector("#totals-table tbody");
    tbody.innerHTML = years
      .map((y) => {
        const t = data[y].totals;
        const r1 = pct(t.seleccionados, t.aspirantes);
        const r2 = pct(t.seleccionados, t.oferta);
        return `<tr>
        <td><span class="year-swatch" style="background:${seriesColor(y)}"></span>${y}</td>
        <td>${nfInt.format(t.aspirantes)}</td>
        <td>${nfInt.format(t.presentaronExamen)}</td>
        <td>${nfInt.format(t.oferta)}</td>
        <td>${nfInt.format(t.seleccionados)}</td>
        <td>${r1 != null ? r1.toFixed(1) + "%" : "—"}</td>
        <td>${r2 != null ? r2.toFixed(1) + "%" : "—"}</td>
      </tr>`;
      })
      .join("");
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
  resetBtn.addEventListener("click", () => {
    carreraSelect.value = ALL_KEY;
    populatePlanteles();
    fullRender();
  });

  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fullRender);
  }

  populatePlanteles();
  fullRender();
})();
