"""Generate the standalone and served visual dashboard for GridWise."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "fixtures" / "public_cases.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GridWise Energy Optimization Visualizer</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border-color: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
    }
    body {
      background: var(--bg);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .custom-scrollbar::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
      background: #475569;
      border-radius: 4px;
    }
  </style>
</head>
<body class="p-4 md:p-6 custom-scrollbar">
  <div class="max-w-7xl mx-auto space-y-6">
    
    <!-- Header -->
    <header class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-lg backdrop-blur">
      <div>
        <div class="flex items-center gap-3">
          <div class="p-2 bg-gradient-to-tr from-amber-500 to-emerald-500 rounded-xl shadow-md">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
          </div>
          <div>
            <h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              GridWise
              <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium border border-emerald-500/30">Optimal Dispatch</span>
            </h1>
            <p class="text-sm text-slate-400">LLM-Assisted Campus Energy Optimization & LP Dispatch</p>
          </div>
        </div>
      </div>

      <!-- Case Selector -->
      <div class="flex items-center gap-3">
        <label for="caseSelect" class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Scenario:</label>
        <select id="caseSelect" class="bg-slate-900 border border-slate-700 text-slate-100 font-medium rounded-xl px-3.5 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none transition">
          <!-- Populated by JS -->
        </select>
        <button id="refreshBtn" onclick="renderCurrentCase()" class="p-2 bg-slate-700/80 hover:bg-slate-700 text-slate-300 rounded-xl transition" title="Reload View">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </header>

    <!-- Top KPI Grid -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Grid Cost</div>
        <div id="kpiCost" class="text-2xl font-black text-amber-400 mt-1">-- BDT</div>
        <div class="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
          <span class="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span> Optimal 24h Tariff
        </div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Grid Draw</div>
        <div id="kpiGrid" class="text-2xl font-black text-blue-400 mt-1">-- kWh</div>
        <div class="text-xs text-slate-500 mt-0.5">Peak: <span id="kpiPeak" class="text-slate-300 font-semibold">--</span> kWh</div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Solar Utilized</div>
        <div id="kpiSolar" class="text-2xl font-black text-amber-300 mt-1">-- kWh</div>
        <div class="text-xs text-slate-500 mt-0.5">Zero curtailment of allowed PV</div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Battery Neutrality</div>
        <div id="kpiBattery" class="text-2xl font-black text-emerald-400 mt-1">100% OK</div>
        <div id="kpiBatterySub" class="text-xs text-slate-500 mt-0.5">E(23) == E(initial)</div>
      </div>
    </div>

    <!-- Directives & Operator Notes Bar -->
    <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 shadow-md">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-bold tracking-wide uppercase text-slate-300 flex items-center gap-2">
          <svg class="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          Operator Notes & LLM Directive Extraction
        </h3>
        <span id="directiveCount" class="text-xs px-2.5 py-0.5 rounded-full bg-slate-700 text-slate-300 font-medium">0 notes</span>
      </div>
      <div id="directivesList" class="space-y-2.5">
        <!-- Injected by JS -->
      </div>
    </div>

    <!-- Main Chart: 24-Hour Energy Balance -->
    <div class="bg-slate-800/70 border border-slate-700/70 rounded-2xl p-5 shadow-lg space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h3 class="text-base font-bold text-white flex items-center gap-2">
            <span>24-Hour Energy Dispatch (Demand vs. Generation & Storage)</span>
          </h3>
          <p class="text-xs text-slate-400">Demand is fulfilled every hour by Solar + Battery Discharge + Grid Import.</p>
        </div>
        <!-- Legend -->
        <div class="flex flex-wrap items-center gap-3 text-xs">
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-amber-400 inline-block shadow-sm"></span> Solar Used</div>
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-emerald-500 inline-block shadow-sm"></span> Battery Discharge</div>
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-blue-500 inline-block shadow-sm"></span> Grid Import</div>
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-purple-500 inline-block shadow-sm"></span> Battery Charge</div>
          <div class="flex items-center gap-1.5"><span class="w-4 h-0.5 bg-rose-400 inline-block"></span> Demand Line</div>
        </div>
      </div>

      <!-- Canvas Container -->
      <div class="relative w-full h-80 bg-slate-900/90 rounded-xl p-3 border border-slate-800">
        <canvas id="dispatchChart" class="w-full h-full block"></canvas>
      </div>
      <div id="chartTooltip" class="text-xs text-slate-400 text-center italic">Hover over any hour column to view the exact flow values.</div>
    </div>

    <!-- Dual Charts: Battery SoC and Tariff Arbitrage -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <!-- Battery SoC Curve -->
      <div class="bg-slate-800/70 border border-slate-700/70 rounded-2xl p-5 shadow-lg space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            Battery State of Charge (kWh)
          </h3>
          <span id="batterySpec" class="text-xs font-mono text-slate-400">Cap: -- kWh</span>
        </div>
        <p class="text-xs text-slate-400">Maintains active reserve floor, never exceeds capacity, and perfectly satisfies E(23) = E(initial).</p>
        <div class="relative w-full h-64 bg-slate-900/90 rounded-xl p-3 border border-slate-800">
          <canvas id="batteryChart" class="w-full h-full block"></canvas>
        </div>
      </div>

      <!-- Tariff Arbitrage Chart -->
      <div class="bg-slate-800/70 border border-slate-700/70 rounded-2xl p-5 shadow-lg space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
            Tariff Arbitrage Strategy (BDT/kWh)
          </h3>
          <span class="text-xs font-mono text-amber-400">Charge Low, Discharge High</span>
        </div>
        <p class="text-xs text-slate-400">Visual proof of LP optimality: battery absorbs low-tariff electricity and discharges during peak-tariff hours.</p>
        <div class="relative w-full h-64 bg-slate-900/90 rounded-xl p-3 border border-slate-800">
          <canvas id="tariffChart" class="w-full h-full block"></canvas>
        </div>
      </div>

    </div>

    <!-- Hourly Plan Table -->
    <div class="bg-slate-800/70 border border-slate-700/70 rounded-2xl p-5 shadow-lg space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-bold uppercase tracking-wider text-slate-300">24-Hour Dispatch Log</h3>
        <span class="text-xs text-slate-400">All values in kWh · Tariffs in BDT</span>
      </div>
      <div class="overflow-x-auto custom-scrollbar rounded-xl border border-slate-700">
        <table class="w-full text-xs text-left font-mono">
          <thead class="bg-slate-900/90 text-slate-400 border-b border-slate-700">
            <tr>
              <th class="py-2.5 px-3">Hour</th>
              <th class="py-2.5 px-3 text-rose-400">Demand</th>
              <th class="py-2.5 px-3 text-amber-400">Solar Avail</th>
              <th class="py-2.5 px-3 text-amber-300">Solar Used</th>
              <th class="py-2.5 px-3 text-purple-400">Action</th>
              <th class="py-2.5 px-3 text-purple-300">Battery kWh</th>
              <th class="py-2.5 px-3 text-emerald-400">Battery SoC</th>
              <th class="py-2.5 px-3 text-blue-400">Grid Import</th>
              <th class="py-2.5 px-3 text-amber-400">Tariff</th>
              <th class="py-2.5 px-3 text-right">Cost (BDT)</th>
            </tr>
          </thead>
          <tbody id="planTableBody" class="divide-y divide-slate-800/80 bg-slate-900/40">
            <!-- Populated by JS -->
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <script>
    const CASES = __CASES_JSON__;

    const caseSelect = document.getElementById("caseSelect");
    CASES.forEach((c, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = `${c.id} - ${c.input.scenario_id}`;
      caseSelect.appendChild(opt);
    });

    caseSelect.addEventListener("change", () => {
      renderCurrentCase();
    });

    function renderCurrentCase() {
      const caseIdx = parseInt(caseSelect.value, 10);
      const data = CASES[caseIdx];
      const inp = data.input;
      const out = data.expected_output;

      // Update KPIs
      document.getElementById("kpiCost").textContent = `${out.total_cost_bdt.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} BDT`;
      document.getElementById("kpiGrid").textContent = `${out.total_grid_kwh.toFixed(1)} kWh`;
      document.getElementById("kpiPeak").textContent = out.peak_grid_kwh.toFixed(1);
      
      const totalSolar = out.hourly_plan.reduce((sum, h) => sum + h.solar_used_kwh, 0);
      document.getElementById("kpiSolar").textContent = `${totalSolar.toFixed(1)} kWh`;
      
      const initE = inp.battery.initial_energy_kwh;
      const finalE = out.hourly_plan[23].battery_energy_after_kwh;
      const neutral = Math.abs(finalE - initE) < 0.02;
      document.getElementById("kpiBattery").textContent = neutral ? "100% OK" : "DRIFT!";
      document.getElementById("kpiBattery").className = neutral ? "text-2xl font-black text-emerald-400 mt-1" : "text-2xl font-black text-rose-500 mt-1";
      document.getElementById("kpiBatterySub").textContent = `Start: ${initE} kWh · End: ${finalE} kWh`;
      document.getElementById("batterySpec").textContent = `Cap: ${inp.battery.capacity_kwh} kWh · Min: ${inp.battery.minimum_energy_kwh} kWh`;

      // Render Directives
      const dirContainer = document.getElementById("directivesList");
      dirContainer.innerHTML = "";
      document.getElementById("directiveCount").textContent = `${inp.operator_notes.length} notes`;

      inp.operator_notes.forEach((note, idx) => {
        const interp = out.directive_interpretation[idx] || {directive_type: "no_op", applies: false, explanation: ""};
        const item = document.createElement("div");
        item.className = "flex flex-col sm:flex-row sm:items-start justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-slate-700/60 text-xs";
        
        let badgeColor = "bg-slate-700 text-slate-300";
        if (interp.directive_type === "solar_reduction") badgeColor = "bg-amber-500/20 text-amber-300 border border-amber-500/30";
        else if (interp.directive_type === "minimum_battery_reserve") badgeColor = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
        else if (interp.directive_type === "no_charge_window") badgeColor = "bg-rose-500/20 text-rose-300 border border-rose-500/30";
        else if (interp.directive_type === "no_discharge_window") badgeColor = "bg-purple-500/20 text-purple-300 border border-purple-500/30";
        else if (interp.directive_type === "max_grid_window") badgeColor = "bg-blue-500/20 text-blue-300 border border-blue-500/30";

        let adjDetails = "";
        if (interp.structured_adjustment) {
          const adj = interp.structured_adjustment;
          const hrs = (adj.hours || []).join(", ");
          if (adj.factor !== undefined) adjDetails = `Hours [${hrs}], Factor: ${adj.factor}`;
          else if (adj.minimum_energy_kwh !== undefined) adjDetails = `Hours [${hrs}], Min Reserve: ${adj.minimum_energy_kwh} kWh`;
          else if (adj.max_grid_kwh !== undefined) adjDetails = `Hours [${hrs}], Cap: ${adj.max_grid_kwh} kWh`;
          else adjDetails = `Hours [${hrs}]`;
        }

        item.innerHTML = `
          <div class="space-y-1">
            <div class="text-slate-200 font-medium">"${note}"</div>
            <div class="text-slate-400 text-[11px]">${interp.explanation || "Interpreted via schema rules."}</div>
          </div>
          <div class="flex sm:flex-col items-end gap-1.5 shrink-0">
            <span class="px-2.5 py-1 rounded-full font-semibold uppercase tracking-wider text-[10px] ${badgeColor}">
              ${interp.directive_type}
            </span>
            ${adjDetails ? `<span class="text-[10px] font-mono text-slate-400">${adjDetails}</span>` : ""}
          </div>
        `;
        dirContainer.appendChild(item);
      });

      // Render Table
      const tbody = document.getElementById("planTableBody");
      tbody.innerHTML = "";
      out.hourly_plan.forEach((p, h) => {
        const inpHour = inp.hours[h];
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-800/50 transition";
        const cost = p.grid_kwh * inpHour.tariff_bdt_per_kwh;
        
        let actClass = "text-slate-400";
        if (p.battery_action === "charge") actClass = "text-purple-400 font-semibold";
        else if (p.battery_action === "discharge") actClass = "text-emerald-400 font-semibold";

        tr.innerHTML = `
          <td class="py-2 px-3 text-slate-300 font-bold">${String(h).padStart(2, '0')}:00</td>
          <td class="py-2 px-3 text-rose-300">${inpHour.demand_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 text-amber-500">${inpHour.solar_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 text-amber-300 font-medium">${p.solar_used_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 ${actClass}">${p.battery_action.toUpperCase()}</td>
          <td class="py-2 px-3 text-purple-300">${p.battery_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 text-emerald-300 font-semibold">${p.battery_energy_after_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 text-blue-300 font-medium">${p.grid_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 text-amber-400">${inpHour.tariff_bdt_per_kwh.toFixed(1)}</td>
          <td class="py-2 px-3 text-right font-medium text-slate-200">${cost.toFixed(2)}</td>
        `;
        tbody.appendChild(tr);
      });

      // Draw Charts
      drawDispatchChart(inp, out);
      drawBatteryChart(inp, out);
      drawTariffChart(inp, out);
    }

    // Canvas Draw Helpers
    function drawDispatchChart(inp, out) {
      const canvas = document.getElementById("dispatchChart");
      const ctx = canvas.getContext("2d");
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const W = rect.width;
      const H = rect.height;
      ctx.clearRect(0, 0, W, H);

      const padL = 45, padR = 15, padT = 20, padB = 30;
      const chartW = W - padL - padR;
      const chartH = H - padT - padB;

      // Find max demand or supply
      let maxVal = 0;
      for (let h = 0; h < 24; h++) {
        const p = out.hourly_plan[h];
        const sum = p.solar_used_kwh + (p.battery_action === "discharge" ? p.battery_kwh : 0) + p.grid_kwh;
        maxVal = Math.max(maxVal, sum, inp.hours[h].demand_kwh);
      }
      maxVal = Math.ceil(maxVal * 1.15 / 50) * 50 || 100;

      // Draw grid lines
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 0.5;
      ctx.fillStyle = "#64748b";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "right";

      const gridSteps = 4;
      for (let i = 0; i <= gridSteps; i++) {
        const yVal = (maxVal / gridSteps) * i;
        const y = padT + chartH - (i / gridSteps) * chartH;
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(padL + chartW, y);
        ctx.stroke();
        ctx.fillText(Math.round(yVal), padL - 8, y + 3);
      }

      // X-axis hours
      const barW = chartW / 24;
      ctx.textAlign = "center";
      for (let h = 0; h < 24; h++) {
        const x = padL + h * barW + barW / 2;
        if (h % 2 === 0) {
          ctx.fillText(h + "h", x, padT + chartH + 18);
        }
      }

      // Draw stacked bars: Solar (bottom), Battery Discharge (middle), Grid (top)
      for (let h = 0; h < 24; h++) {
        const p = out.hourly_plan[h];
        const x = padL + h * barW + 2;
        const w = barW - 4;
        let curY = padT + chartH;

        // 1. Solar Used
        const sH = (p.solar_used_kwh / maxVal) * chartH;
        if (sH > 0) {
          ctx.fillStyle = "#f59e0b";
          ctx.fillRect(x, curY - sH, w, sH);
          curY -= sH;
        }

        // 2. Battery Discharge
        if (p.battery_action === "discharge" && p.battery_kwh > 0) {
          const dH = (p.battery_kwh / maxVal) * chartH;
          ctx.fillStyle = "#10b981";
          ctx.fillRect(x, curY - dH, w, dH);
          curY -= dH;
        }

        // 3. Grid Import
        const gH = (p.grid_kwh / maxVal) * chartH;
        if (gH > 0) {
          ctx.fillStyle = "#3b82f6";
          ctx.fillRect(x, curY - gH, w, gH);
          curY -= gH;
        }

        // Battery Charge outline / indicator below
        if (p.battery_action === "charge" && p.battery_kwh > 0) {
          const cH = (p.battery_kwh / maxVal) * chartH;
          ctx.strokeStyle = "#a855f7";
          ctx.lineWidth = 1.5;
          ctx.setLineDash([2, 2]);
          ctx.strokeRect(x, padT + chartH - cH, w, cH);
          ctx.setLineDash([]);
        }
      }

      // Draw Demand line
      ctx.beginPath();
      ctx.strokeStyle = "#f43f5e";
      ctx.lineWidth = 2.5;
      for (let h = 0; h < 24; h++) {
        const d = inp.hours[h].demand_kwh;
        const x = padL + h * barW + barW / 2;
        const y = padT + chartH - (d / maxVal) * chartH;
        if (h === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Demand points
      ctx.fillStyle = "#f43f5e";
      for (let h = 0; h < 24; h++) {
        const d = inp.hours[h].demand_kwh;
        const x = padL + h * barW + barW / 2;
        const y = padT + chartH - (d / maxVal) * chartH;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawBatteryChart(inp, out) {
      const canvas = document.getElementById("batteryChart");
      const ctx = canvas.getContext("2d");
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const W = rect.width;
      const H = rect.height;
      ctx.clearRect(0, 0, W, H);

      const padL = 40, padR = 15, padT = 20, padB = 30;
      const chartW = W - padL - padR;
      const chartH = H - padT - padB;
      const cap = inp.battery.capacity_kwh;
      const maxVal = cap * 1.1;

      // Axis lines
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 0.5;
      ctx.fillStyle = "#64748b";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "right";

      for (let i = 0; i <= 4; i++) {
        const yVal = (cap / 4) * i;
        const y = padT + chartH - (yVal / maxVal) * chartH;
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(padL + chartW, y);
        ctx.stroke();
        ctx.fillText(Math.round(yVal), padL - 8, y + 3);
      }

      // X-axis hours
      const stepX = chartW / 23;
      ctx.textAlign = "center";
      for (let h = 0; h < 24; h += 3) {
        const x = padL + h * stepX;
        ctx.fillText(h + "h", x, padT + chartH + 18);
      }

      // Capacity line
      const capY = padT + chartH - (cap / maxVal) * chartH;
      ctx.strokeStyle = "#94a3b8";
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padL, capY);
      ctx.lineTo(padL + chartW, capY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Fill SoC Area
      ctx.beginPath();
      ctx.moveTo(padL, padT + chartH);
      for (let h = 0; h < 24; h++) {
        const e = out.hourly_plan[h].battery_energy_after_kwh;
        const x = padL + h * stepX;
        const y = padT + chartH - (e / maxVal) * chartH;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(padL + 23 * stepX, padT + chartH);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, padT, 0, padT + chartH);
      grad.addColorStop(0, "rgba(16, 185, 129, 0.4)");
      grad.addColorStop(1, "rgba(16, 185, 129, 0.05)");
      ctx.fillStyle = grad;
      ctx.fill();

      // Draw SoC Line
      ctx.beginPath();
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2.5;
      for (let h = 0; h < 24; h++) {
        const e = out.hourly_plan[h].battery_energy_after_kwh;
        const x = padL + h * stepX;
        const y = padT + chartH - (e / maxVal) * chartH;
        if (h === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Mark Initial and Final
      const initY = padT + chartH - (inp.battery.initial_energy_kwh / maxVal) * chartH;
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.arc(padL, initY, 5, 0, Math.PI * 2);
      ctx.fill();
      const finalY = padT + chartH - (out.hourly_plan[23].battery_energy_after_kwh / maxVal) * chartH;
      ctx.beginPath();
      ctx.arc(padL + 23 * stepX, finalY, 5, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawTariffChart(inp, out) {
      const canvas = document.getElementById("tariffChart");
      const ctx = canvas.getContext("2d");
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const W = rect.width;
      const H = rect.height;
      ctx.clearRect(0, 0, W, H);

      const padL = 35, padR = 15, padT = 20, padB = 30;
      const chartW = W - padL - padR;
      const chartH = H - padT - padB;

      let maxT = Math.max(...inp.hours.map(h => h.tariff_bdt_per_kwh));
      maxT = Math.ceil(maxT * 1.2 / 2) * 2 || 10;

      // Grid lines
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 0.5;
      ctx.fillStyle = "#64748b";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "right";

      for (let i = 0; i <= 3; i++) {
        const yVal = (maxT / 3) * i;
        const y = padT + chartH - (i / 3) * chartH;
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(padL + chartW, y);
        ctx.stroke();
        ctx.fillText(Math.round(yVal), padL - 6, y + 3);
      }

      const barW = chartW / 24;
      ctx.textAlign = "center";
      for (let h = 0; h < 24; h++) {
        const t = inp.hours[h].tariff_bdt_per_kwh;
        const act = out.hourly_plan[h].battery_action;
        const x = padL + h * barW + 2;
        const w = barW - 4;
        const bH = (t / maxT) * chartH;
        const y = padT + chartH - bH;

        // Color tariff bar based on battery decision:
        // Charge when low tariff -> purple badge
        // Discharge when high tariff -> emerald badge
        // Else neutral amber/slate
        if (act === "charge") ctx.fillStyle = "#a855f7";
        else if (act === "discharge") ctx.fillStyle = "#10b981";
        else ctx.fillStyle = "#475569";

        ctx.fillRect(x, y, w, bH);

        if (h % 2 === 0) {
          ctx.fillStyle = "#64748b";
          ctx.fillText(h + "h", x + w / 2, padT + chartH + 18);
        }
      }
    }

    // Initial Render
    window.addEventListener("DOMContentLoaded", () => {
      renderCurrentCase();
    });
    window.addEventListener("resize", () => {
      renderCurrentCase();
    });
  </script>
</body>
</html>
"""

def generate():
    cases_json_str = json.dumps(CASES)
    full_html = HTML_TEMPLATE.replace("__CASES_JSON__", cases_json_str)

    # 1. Save in app/dashboard.html (for FastAPI web service)
    app_target = ROOT / "app" / "dashboard.html"
    app_target.write_text(full_html, encoding="utf-8")
    print(f"Generated web dashboard: {app_target} ({len(full_html)} bytes)")

    # 2. Save in brain artifacts folder for user & inline embedding
    brain_target = Path(r"C:\Users\MSI\.gemini\antigravity\brain\157bb21b-8415-4417-91a6-4461658f20a8\gridwise_dashboard.html")
    brain_target.write_text(full_html, encoding="utf-8")
    print(f"Generated artifact dashboard: {brain_target} ({len(full_html)} bytes)")

if __name__ == "__main__":
    generate()
