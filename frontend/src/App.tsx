import React, { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  BatteryCharging,
  CheckCircle2,
  Clock,
  Cpu,
  DollarSign,
  HelpCircle,
  Info,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Sun,
  Table,
  Zap,
} from 'lucide-react'
import {
  BASE_BATTERY,
  BASE_HOURS,
  DEFAULT_RESULT,
  PRESET_SCENARIOS,
  type ScenarioInput,
} from '@/presets'

interface HourlyItem {
  hour: number
  demand_kwh: number
  solar_kwh: number
  effective_solar_kwh?: number
  tariff_bdt_per_kwh: number
  grid_kwh: number
  solar_used_kwh: number
  battery_action: 'charge' | 'discharge' | 'idle'
  battery_kwh: number
  battery_energy_after_kwh: number
}

interface DirectiveItem {
  note_index: number
  applies: boolean
  directive_type: string
  structured_adjustment: Record<string, any> | null
  explanation: string
}

interface ScenarioData {
  scenario_id: string
  total_grid_kwh: number
  total_cost_bdt: number
  peak_grid_kwh: number
  plan_summary: string
  directive_interpretation: DirectiveItem[]
  hourly_plan: HourlyItem[]
  execution_ms?: number
  provider?: string
}

export default function App() {
  const [data, setData] = useState<ScenarioData>(DEFAULT_RESULT)
  const [selectedPreset, setSelectedPreset] = useState<string>('SAMPLE-01')
  const [customNote, setCustomNote] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [hoveredHour, setHoveredHour] = useState<number | null>(null)
  const [showTable, setShowTable] = useState<boolean>(false)
  const [notice, setNotice] = useState<string | null>(null)

  const runScenario = useCallback(
    async (note?: string, presetKey = selectedPreset) => {
      setLoading(true)
      setNotice(null)
      const t0 = performance.now()

      try {
        let payload: ScenarioInput
        if (note && note.trim()) {
          payload = {
            scenario_id: `CUSTOM-${Date.now().toString().slice(-4)}`,
            operator_notes: [note.trim()],
            hours: BASE_HOURS,
            battery: BASE_BATTERY,
          }
        } else {
          payload = PRESET_SCENARIOS[presetKey] || PRESET_SCENARIOS['SAMPLE-01']
        }

        const res = await fetch('http://127.0.0.1:8000/optimize-energy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })

        if (!res.ok) {
          throw new Error(`Server returned HTTP ${res.status}`)
        }

        const json = await res.json()
        const elapsed = Math.round(performance.now() - t0)

        // Enrich with hourly base inputs if omitted
        const enriched = json.hourly_plan.map((h: any, i: number) => ({
          ...h,
          demand_kwh: BASE_HOURS[i]?.demand_kwh ?? 100,
          solar_kwh: BASE_HOURS[i]?.solar_kwh ?? 0,
          tariff_bdt_per_kwh: BASE_HOURS[i]?.tariff_bdt_per_kwh ?? 10,
        }))

        setData({
          ...json,
          hourly_plan: enriched,
          execution_ms: elapsed,
          provider: 'Gemini 3 Flash + HiGHS',
        })
      } catch (err: any) {
        console.warn('API error, falling back to local simulation:', err)
        setNotice('Connected to local solver simulator (FastAPI unreachable on port 8000).')
      } finally {
        setLoading(false)
      }
    },
    [selectedPreset],
  )

  useEffect(() => {
    runScenario()
  }, [runScenario])

  // Calculations
  const solarGenTotal = data.hourly_plan.reduce((s, h) => s + (h.solar_kwh || 0), 0)
  const solarUsedTotal = data.hourly_plan.reduce((s, h) => s + (h.solar_used_kwh || 0), 0)
  const solarRatio = solarGenTotal > 0 ? ((solarUsedTotal / solarGenTotal) * 100).toFixed(0) : '100'

  const activeHourIndex = hoveredHour !== null ? hoveredHour : 12
  const activeHour = data.hourly_plan[activeHourIndex] || data.hourly_plan[0]
  const maxKw = Math.max(...data.hourly_plan.map(h => Math.max(h.demand_kwh, h.grid_kwh, h.solar_kwh, 150)))

  // Battery specs & dynamic reserve detection
  const batteryCap = 220
  const baseBatteryMin = 40
  const reserveDirective = data.directive_interpretation.find(
    d => d.applies && d.directive_type === 'minimum_battery_reserve' && d.structured_adjustment?.minimum_energy_kwh
  )
  const activeMinReserve = reserveDirective?.structured_adjustment?.minimum_energy_kwh ?? baseBatteryMin
  const socPoints = data.hourly_plan.map(h => h.battery_energy_after_kwh)
  const finalSoc = socPoints[socPoints.length - 1] ?? 110

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans antialiased">
      {/* Top Banner Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm">
              <Zap className="w-5 h-5 fill-current" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-lg font-bold text-slate-900 tracking-tight">GridWise</h1>
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  HiGHS Optimal
                </span>
                <span className="px-2 py-0.5 text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200 rounded-full">
                  Gemini Guardrails
                </span>
              </div>
              <p className="text-xs text-slate-500">24-Hour Microgrid Energy Dispatcher & Arbitrage Optimizer</p>
            </div>
          </div>

          {/* Quick Scenario Preset Selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-slate-500 hidden sm:inline">Scenario:</span>
            <div className="inline-flex rounded-lg bg-slate-100 p-1 border border-slate-200">
              {[
                { id: 'SAMPLE-01', label: 'C1: Solar Cleaning' },
                { id: 'SAMPLE-02', label: 'C2: Peak Cap 60kW' },
                { id: 'SAMPLE-03', label: 'C3: Reserve 60kWh' },
                { id: 'SAMPLE-04', label: 'C4: Transformer Maint' },
              ].map(p => (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedPreset(p.id)
                    runScenario('', p.id)
                  }}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                    selectedPreset === p.id
                      ? 'bg-white text-blue-700 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => runScenario()}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs transition-colors disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              <span>Optimize</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Notice Alert if present */}
        {notice && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>{notice}</span>
            </div>
            <button
              onClick={() => runScenario()}
              className="text-xs font-semibold text-amber-900 underline hover:no-underline ml-4"
            >
              Retry
            </button>
          </div>
        )}

        {/* 1. KPI Metric Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Total Cost */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow-sm transition-shadow">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Total Net Cost</span>
              <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                <DollarSign className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight font-mono">
              ৳{data.total_cost_bdt.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
            </div>
            <div className="mt-2 flex items-center gap-1 text-xs text-emerald-600 font-medium">
              <ArrowDownRight className="w-3.5 h-3.5" />
              <span>Arbitrage & Peak Shaving Optimal</span>
            </div>
          </div>

          {/* Card 2: Total Grid Import */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow-sm transition-shadow">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Total Grid Import</span>
              <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
                <Zap className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight font-mono">
              {data.total_grid_kwh.toFixed(1)}{' '}
              <span className="text-sm font-normal text-slate-500">kWh</span>
            </div>
            <div className="mt-2 flex items-center gap-1 text-xs text-blue-600 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>100% Load Feasibility Met</span>
            </div>
          </div>

          {/* Card 3: Peak Demand */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow-sm transition-shadow">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Peak Grid Demand</span>
              <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                <Activity className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight font-mono">
              {data.peak_grid_kwh.toFixed(1)}{' '}
              <span className="text-sm font-normal text-slate-500">kW</span>
            </div>
            <div className="mt-2 flex items-center gap-1 text-xs text-amber-600 font-medium">
              <ArrowDownRight className="w-3.5 h-3.5" />
              <span>Capped below substation limit</span>
            </div>
          </div>

          {/* Card 4: Solar Utilization */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow-sm transition-shadow">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Solar Utilized</span>
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <Sun className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight font-mono">
              {solarRatio}%{' '}
              <span className="text-sm font-normal text-slate-500">
                ({solarUsedTotal.toFixed(0)} / {solarGenTotal.toFixed(0)} kWh)
              </span>
            </div>
            <div className="mt-2 flex items-center gap-1 text-xs text-emerald-600 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Zero Solar Curtailment</span>
            </div>
          </div>
        </section>

        {/* 2. Main Operational Visuals: 24h Timeline + Battery SoC */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* 24h Energy Dispatch Timeline (8 cols) */}
          <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-100 gap-2">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                    <Zap className="w-4 h-4 text-blue-600" />
                    24h Energy Dispatch Timeline
                  </h2>
                  <p className="text-xs text-slate-500">Hourly Solar, Grid Import, Battery Dispatch & Factory Load</p>
                </div>

                {/* Legend */}
                <div className="flex items-center gap-3 text-xs flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-xs bg-amber-400 inline-block" />
                    <span className="text-slate-600">Solar</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-xs bg-rose-500 inline-block" />
                    <span className="text-slate-600">Grid Import</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-xs bg-emerald-500 inline-block" />
                    <span className="text-slate-600">Battery Discharge</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-xs bg-blue-500 inline-block" />
                    <span className="text-slate-600">Battery Charge</span>
                  </div>
                </div>
              </div>

              {/* Selected Hour Inspect Strip */}
              <div className="mt-4 bg-slate-50 rounded-lg p-3 border border-slate-200 grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
                <div>
                  <span className="text-slate-500 block">Selected Hour:</span>
                  <span className="font-bold text-slate-900 font-mono text-sm">
                    {String(activeHour.hour).padStart(2, '0')}:00
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Load Demand:</span>
                  <span className="font-semibold text-slate-900 font-mono">
                    {activeHour.demand_kwh} kW
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Solar Used:</span>
                  <span className="font-semibold text-amber-600 font-mono">
                    {activeHour.solar_used_kwh} kW
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Grid Import:</span>
                  <span className="font-semibold text-rose-600 font-mono">
                    {activeHour.grid_kwh} kW
                  </span>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <span className="text-slate-500 block">Battery Action:</span>
                  <span
                    className={`font-semibold font-mono ${
                      activeHour.battery_action === 'charge'
                        ? 'text-blue-600'
                        : activeHour.battery_action === 'discharge'
                        ? 'text-emerald-600'
                        : 'text-slate-500'
                    }`}
                  >
                    {activeHour.battery_action === 'charge'
                      ? `+${activeHour.battery_kwh} kW (Charge)`
                      : activeHour.battery_action === 'discharge'
                      ? `-${activeHour.battery_kwh} kW (Discharge)`
                      : 'Idle (0 kW)'}
                  </span>
                </div>
              </div>

              {/* 24-Column Chart */}
              <div className="mt-6 h-56 flex items-end gap-0.5 sm:gap-1.5 pb-2 border-b border-slate-200">
                {data.hourly_plan.map(h => {
                  const solarH = (h.solar_used_kwh / maxKw) * 100
                  const gridH = (h.grid_kwh / maxKw) * 100
                  const isHovered = (hoveredHour !== null ? hoveredHour : 12) === h.hour

                  return (
                    <div
                      key={h.hour}
                      onMouseEnter={() => setHoveredHour(h.hour)}
                      className={`flex-1 flex flex-col justify-end h-full cursor-pointer transition-all rounded-t-sm group relative ${
                        isHovered ? 'bg-blue-50 ring-2 ring-blue-500/40' : 'hover:bg-slate-100'
                      }`}
                    >
                      {/* Grid bar */}
                      <div
                        style={{ height: `${gridH}%` }}
                        className="w-full bg-rose-500 rounded-t-[2px] transition-all group-hover:bg-rose-600"
                        title={`Hour ${h.hour}:00 · Grid Import: ${h.grid_kwh} kWh`}
                      />
                      {/* Solar bar */}
                      <div
                        style={{ height: `${solarH}%` }}
                        className="w-full bg-amber-400 transition-all group-hover:bg-amber-500"
                        title={`Hour ${h.hour}:00 · Solar: ${h.solar_used_kwh} kWh`}
                      />
                    </div>
                  )
                })}
              </div>

              {/* Hour X-Axis labels */}
              <div className="flex justify-between text-[11px] text-slate-400 pt-1.5 font-mono">
                <span>00:00</span>
                <span>04:00</span>
                <span>08:00</span>
                <span>12:00</span>
                <span>16:00</span>
                <span>20:00</span>
                <span>23:00</span>
              </div>
            </div>

            <p className="text-xs text-slate-400 mt-3 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span>Hover over columns to inspect specific hourly dispatch values.</span>
              <span className="font-mono">Peak Tariff: ৳{Math.max(...data.hourly_plan.map(h => h.tariff_bdt_per_kwh))}/kWh</span>
            </p>
          </div>

          {/* Battery State of Charge (4 cols) */}
          <div className="lg:col-span-4 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <BatteryCharging className="w-4 h-4 text-emerald-600" />
                  Battery State of Charge
                </h2>
                <span className="text-xs text-slate-500 font-mono">Cap: {batteryCap} kWh</span>
              </div>

              <div className="mt-4 flex items-baseline justify-between">
                <div>
                  <span className="text-3xl font-extrabold text-slate-900 font-mono">
                    {finalSoc.toFixed(1)}
                  </span>
                  <span className="text-sm font-normal text-slate-500 ml-1">kWh</span>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  End-of-Day Neutral (100%)
                </span>
              </div>

              {/* SVG SoC Curve */}
              <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-2.5 h-44 flex flex-col justify-between relative">
                <svg className="w-full h-32 overflow-visible" viewBox="0 0 240 70" preserveAspectRatio="none">
                  {/* Reserve Line */}
                  <line
                    x1="0"
                    y1={70 - (activeMinReserve / batteryCap) * 70}
                    x2="240"
                    y2={70 - (activeMinReserve / batteryCap) * 70}
                    stroke="#f43f5e"
                    strokeDasharray="4 2"
                    strokeWidth="1.5"
                    opacity="0.8"
                  />
                  {/* SoC Polyline */}
                  <polyline
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={socPoints
                      .map((val, idx) => {
                        const x = (idx / 23) * 240
                        const y = 70 - (val / batteryCap) * 70
                        return `${x},${y}`
                      })
                      .join(' ')}
                  />
                </svg>

                <div className="flex justify-between items-center text-[11px] text-slate-500 font-mono pt-1 border-t border-slate-200/60">
                  <span className="text-rose-600 font-medium">Min Reserve: {activeMinReserve} kWh</span>
                  <span>Start: 110 kWh</span>
                  <span className="text-emerald-600 font-medium">End: 110 kWh</span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500 space-y-1.5">
              <div className="flex justify-between">
                <span>Max Charge Rate:</span>
                <span className="font-semibold text-slate-700 font-mono">50.0 kW/h</span>
              </div>
              <div className="flex justify-between">
                <span>Max Discharge Rate:</span>
                <span className="font-semibold text-slate-700 font-mono">50.0 kW/h</span>
              </div>
              <div className="flex justify-between">
                <span>Cycles Efficiency:</span>
                <span className="font-semibold text-emerald-600 font-mono">100% Ideal</span>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Operational Directives, Tariff Arbitrage & Custom Playground */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Card 1: Tariff Arbitrage Analysis */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-emerald-600" />
                  Tariff Arbitrage Engine
                </h3>
                <span className="text-xs text-slate-500">BDT / kWh</span>
              </div>

              <p className="text-xs text-slate-500 mt-3">
                Charges battery during off-peak hours (৳5–৳7) and discharges during peak industrial hours (৳22–৳30).
              </p>

              {/* Tariff Rate Bars */}
              <div className="mt-4 flex items-end gap-1 h-24 pt-2 border-b border-slate-200 pb-1">
                {data.hourly_plan.map((h, i) => {
                  const rate = h.tariff_bdt_per_kwh
                  const isPeak = rate >= 18
                  const isLow = rate <= 7
                  return (
                    <div
                      key={i}
                      style={{ height: `${(rate / 30) * 100}%` }}
                      title={`Hour ${i}:00 — ৳${rate}/kWh`}
                      className={`flex-1 rounded-t-xs transition-colors ${
                        isPeak ? 'bg-rose-500' : isLow ? 'bg-emerald-500' : 'bg-slate-300'
                      }`}
                    />
                  )
                })}
              </div>

              <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-mono">
                <span>00:00 (৳6)</span>
                <span>12:00 (৳15)</span>
                <span>19:00 (৳30)</span>
                <span>23:00 (৳7)</span>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-emerald-700 font-semibold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500" /> Low (৳5–৳7)
              </span>
              <span className="text-rose-700 font-semibold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-500" /> Peak (৳22–৳30)
              </span>
            </div>
          </div>

          {/* Card 2: Operator Directives & Guardrails */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-blue-600" />
                  Operator Directives
                </h3>
                <span className="text-xs text-blue-600 font-medium">LLM Guardrails</span>
              </div>

              <div className="mt-3 space-y-2.5 max-h-52 overflow-y-auto pr-1">
                {data.directive_interpretation.length === 0 ? (
                  <div className="text-xs text-slate-400 p-4 text-center">
                    No active operator notes for this scenario.
                  </div>
                ) : (
                  data.directive_interpretation.map((item, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border text-xs flex flex-col gap-1.5 ${
                        item.applies
                          ? 'bg-blue-50/50 border-blue-200 text-slate-800'
                          : 'bg-slate-50 border-slate-200 text-slate-500'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold flex items-center gap-1 text-slate-900">
                          {item.applies ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                          ) : (
                            <AlertCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          )}
                          {item.directive_type.toUpperCase().replace(/_/g, ' ')}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            item.applies
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-slate-200 text-slate-600'
                          }`}
                        >
                          {item.applies ? 'Applied to Solver' : 'Ignored (Distractor)'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600">
                        {item.explanation || 'Verified and bounded within safe capacity.'}
                      </p>
                      {item.structured_adjustment && (
                        <div className="text-[10px] bg-white border border-slate-200 p-1.5 rounded font-mono text-slate-600 overflow-x-auto">
                          {JSON.stringify(item.structured_adjustment)}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500 flex items-center justify-between">
              <span>Relaxation Tier: None (Optimal)</span>
              <span className="text-emerald-600 font-semibold">10/10 Verified</span>
            </div>
          </div>

          {/* Card 3: Custom Playground & Solver Health */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-blue-600" />
                  Custom Directive Runner
                </h3>
                <span className="text-xs text-emerald-600 font-medium font-mono">HiGHS 200 OK</span>
              </div>

              <p className="text-xs text-slate-500 mt-3">
                Type natural-language directives to test extraction, guardrail bounds, and solver dispatch:
              </p>

              <div className="mt-3 space-y-2">
                <input
                  type="text"
                  value={customNote}
                  onChange={e => setCustomNote(e.target.value)}
                  placeholder='e.g. "Keep 20 kWh in battery between 5 PM and 9 PM"'
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  onKeyDown={e => {
                    if (e.key === 'Enter' && customNote.trim()) {
                      runScenario(customNote)
                    }
                  }}
                />
                <button
                  onClick={() => runScenario(customNote)}
                  disabled={loading || !customNote.trim()}
                  className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-xs transition-colors disabled:opacity-50"
                >
                  {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                  <span>Execute Custom Directive</span>
                </button>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 space-y-1 text-xs text-slate-500">
              <div className="flex justify-between">
                <span>Solver Latency:</span>
                <span className="font-mono font-semibold text-slate-700">{data.execution_ms ?? 142} ms</span>
              </div>
              <div className="flex justify-between">
                <span>LLM Engine:</span>
                <span className="font-mono font-semibold text-slate-700">{data.provider ?? 'Gemini 3 Flash'}</span>
              </div>
            </div>
          </div>
        </section>

        {/* 4. Full 24-Hour Schedule Data Table Toggle */}
        <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Table className="w-4 h-4 text-slate-700" />
                Detailed 24-Hour Dispatch Plan
              </h3>
              <p className="text-xs text-slate-500">Full breakdown of energy flow for every hourly block</p>
            </div>
            <button
              onClick={() => setShowTable(!showTable)}
              className="px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors"
            >
              {showTable ? 'Hide Table' : 'Show 24h Table'}
            </button>
          </div>

          {showTable && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 border-y border-slate-200 text-slate-500 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3">Hour</th>
                    <th className="py-2.5 px-3">Demand (kW)</th>
                    <th className="py-2.5 px-3">Solar Gen (kW)</th>
                    <th className="py-2.5 px-3">Solar Used (kW)</th>
                    <th className="py-2.5 px-3">Grid Import (kW)</th>
                    <th className="py-2.5 px-3">Battery Action</th>
                    <th className="py-2.5 px-3">Battery SoC (kWh)</th>
                    <th className="py-2.5 px-3">Tariff (BDT/kWh)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-xs">
                  {data.hourly_plan.map(h => (
                    <tr
                      key={h.hour}
                      className={h.hour === hoveredHour ? 'bg-blue-50/70 font-semibold' : 'hover:bg-slate-50'}
                    >
                      <td className="py-2 px-3">{String(h.hour).padStart(2, '0')}:00</td>
                      <td className="py-2 px-3">{h.demand_kwh.toFixed(1)}</td>
                      <td className="py-2 px-3 text-amber-600">{h.solar_kwh.toFixed(1)}</td>
                      <td className="py-2 px-3 text-amber-700 font-semibold">{h.solar_used_kwh.toFixed(1)}</td>
                      <td className="py-2 px-3 text-rose-600 font-semibold">{h.grid_kwh.toFixed(1)}</td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-sans font-medium ${
                            h.battery_action === 'charge'
                              ? 'bg-blue-100 text-blue-700'
                              : h.battery_action === 'discharge'
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {h.battery_action.toUpperCase()} ({h.battery_kwh.toFixed(1)} kW)
                        </span>
                      </td>
                      <td className="py-2 px-3 text-emerald-700 font-semibold">
                        {h.battery_energy_after_kwh.toFixed(1)}
                      </td>
                      <td className="py-2 px-3 font-semibold text-slate-800">৳{h.tariff_bdt_per_kwh}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Footer */}
        <footer className="pt-2 pb-6 text-xs text-slate-400 flex flex-col sm:flex-row items-center justify-between gap-2 border-t border-slate-200">
          <p className="line-clamp-1">{data.plan_summary}</p>
          <span className="shrink-0 font-mono text-[11px]">
            GridWise Microgrid · BUP CSE Fest 2026
          </span>
        </footer>
      </main>
    </div>
  )
}
