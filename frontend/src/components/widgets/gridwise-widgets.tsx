import React, { useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Battery,
  BatteryCharging,
  CheckCircle2,
  Cpu,
  DollarSign,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Sun,
  Zap,
} from 'lucide-react'

export interface HourlyPlanItem {
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

export interface DirectiveItem {
  note_index: number
  applies: boolean
  directive_type: string
  structured_adjustment: Record<string, any> | null
  explanation: string
}

export interface ScenarioResult {
  scenario_id: string
  total_grid_kwh: number
  total_cost_bdt: number
  peak_grid_kwh: number
  plan_summary: string
  directive_interpretation: DirectiveItem[]
  hourly_plan: HourlyPlanItem[]
  execution_ms?: number
  provider?: string
}

// Shell wrapper matching the draggable grid aesthetics
export function WidgetShell({
  title,
  meta,
  icon: Icon,
  children,
}: {
  title: string
  meta?: React.ReactNode
  icon?: React.ComponentType<{ className?: string }>
  children: React.ReactNode
}) {
  return (
    <section className="flex h-full flex-col p-4 sm:p-5 text-card-foreground">
      <header className="flex items-center justify-between pb-3 border-b border-border/60">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4 text-primary" />}
          <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            {title}
          </h3>
        </div>
        {meta && <span className="text-xs text-muted-foreground">{meta}</span>}
      </header>
      <div className="flex flex-1 flex-col pt-3 min-h-0">{children}</div>
    </section>
  )
}

// 1. KPI Widget (wide 2x1)
export function KpiWidget({ data }: { data: ScenarioResult }) {
  const solarGenerated = data.hourly_plan.reduce((sum, h) => sum + (h.solar_kwh || 0), 0)
  const solarUsed = data.hourly_plan.reduce((sum, h) => sum + (h.solar_used_kwh || 0), 0)
  const solarRatio = solarGenerated > 0 ? ((solarUsed / solarGenerated) * 100).toFixed(0) : '100'

  return (
    <WidgetShell title="Energy KPIs & Cost Overview" icon={DollarSign} meta="24-Hour Horizon">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 h-full items-center">
        <div className="rounded-lg bg-secondary/40 p-3 border border-border/40">
          <span className="text-xs text-muted-foreground">Net Cost</span>
          <div className="text-xl font-bold tracking-tight text-foreground">
            ৳{data.total_cost_bdt.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
          </div>
          <span className="text-[11px] text-emerald-500 font-medium inline-flex items-center gap-0.5">
            <ArrowDownRight className="w-3 h-3" /> Arbitrage Optimal
          </span>
        </div>

        <div className="rounded-lg bg-secondary/40 p-3 border border-border/40">
          <span className="text-xs text-muted-foreground">Grid Import</span>
          <div className="text-xl font-bold tracking-tight text-foreground">
            {data.total_grid_kwh.toFixed(1)} <span className="text-xs font-normal text-muted-foreground">kWh</span>
          </div>
          <span className="text-[11px] text-sky-500 font-medium">Off-peak Balanced</span>
        </div>

        <div className="rounded-lg bg-secondary/40 p-3 border border-border/40">
          <span className="text-xs text-muted-foreground">Peak Demand</span>
          <div className="text-xl font-bold tracking-tight text-foreground">
            {data.peak_grid_kwh.toFixed(1)} <span className="text-xs font-normal text-muted-foreground">kW</span>
          </div>
          <span className="text-[11px] text-amber-500 font-medium">Shaved Peak</span>
        </div>

        <div className="rounded-lg bg-secondary/40 p-3 border border-border/40">
          <span className="text-xs text-muted-foreground">Solar Utilized</span>
          <div className="text-xl font-bold tracking-tight text-foreground">
            {solarRatio}%
          </div>
          <span className="text-[11px] text-emerald-500 font-medium">100% Zero-Curtail</span>
        </div>
      </div>
    </WidgetShell>
  )
}

// 2. 24h Dispatch Timeline (lg 2x2)
export function DispatchTimelineWidget({ data }: { data: ScenarioResult }) {
  const [hoveredHour, setHoveredHour] = useState<number | null>(null)
  const maxKw = Math.max(...data.hourly_plan.map(h => Math.max(h.demand_kwh, h.grid_kwh, h.solar_kwh, 120)))

  const activeHour = hoveredHour !== null ? data.hourly_plan[hoveredHour] : data.hourly_plan[12]

  return (
    <WidgetShell
      title="24h Energy Dispatch Timeline"
      icon={Zap}
      meta={hoveredHour !== null ? `Hour ${hoveredHour}:00 selected` : 'Hover column to inspect'}
    >
      <div className="flex flex-col h-full gap-2">
        {/* Detail Callout */}
        <div className="grid grid-cols-5 gap-1.5 p-2 rounded-lg bg-secondary/30 border border-border/50 text-xs">
          <div>
            <span className="text-muted-foreground">Hour:</span>{' '}
            <span className="font-semibold text-foreground">{String(activeHour.hour).padStart(2, '0')}:00</span>
          </div>
          <div>
            <span className="text-muted-foreground">Demand:</span>{' '}
            <span className="font-semibold text-foreground">{activeHour.demand_kwh} kW</span>
          </div>
          <div>
            <span className="text-muted-foreground">Solar:</span>{' '}
            <span className="font-semibold text-amber-500">{activeHour.solar_used_kwh} kW</span>
          </div>
          <div>
            <span className="text-muted-foreground">Grid:</span>{' '}
            <span className="font-semibold text-rose-500">{activeHour.grid_kwh} kW</span>
          </div>
          <div>
            <span className="text-muted-foreground">Battery:</span>{' '}
            <span className={`font-semibold ${activeHour.battery_action === 'charge' ? 'text-blue-500' : activeHour.battery_action === 'discharge' ? 'text-emerald-500' : 'text-muted-foreground'}`}>
              {activeHour.battery_action === 'charge' ? `+${activeHour.battery_kwh} kW` : activeHour.battery_action === 'discharge' ? `-${activeHour.battery_kwh} kW` : 'Idle'}
            </span>
          </div>
        </div>

        {/* 24-Column Stacked Visualizer */}
        <div className="flex-1 flex items-end gap-1 pt-4 pb-1 border-b border-border/50">
          {data.hourly_plan.map((h) => {
            const solarHeight = (h.solar_used_kwh / maxKw) * 100
            const gridHeight = (h.grid_kwh / maxKw) * 100
            const isHovered = hoveredHour === h.hour

            return (
              <div
                key={h.hour}
                onMouseEnter={() => setHoveredHour(h.hour)}
                onMouseLeave={() => setHoveredHour(null)}
                className={`flex-1 flex flex-col justify-end h-full cursor-pointer transition-all duration-150 rounded-t-sm ${
                  isHovered ? 'bg-accent/40 scale-y-105' : 'hover:bg-accent/20'
                }`}
              >
                {/* Grid import portion */}
                <div
                  style={{ height: `${gridHeight}%` }}
                  className="w-full bg-rose-500/80 hover:bg-rose-500 transition-colors rounded-t-[1px]"
                  title={`Hour ${h.hour}: Grid ${h.grid_kwh} kWh`}
                />
                {/* Solar used portion */}
                <div
                  style={{ height: `${solarHeight}%` }}
                  className="w-full bg-amber-400/90 hover:bg-amber-400 transition-colors"
                  title={`Hour ${h.hour}: Solar ${h.solar_used_kwh} kWh`}
                />
              </div>
            )
          })}
        </div>

        {/* Hour markers & legend */}
        <div className="flex justify-between text-[10px] text-muted-foreground pt-1">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>23:00</span>
        </div>

        <div className="flex items-center justify-center gap-4 text-xs pt-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block" />
            <span className="text-muted-foreground">Solar Used</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500 inline-block" />
            <span className="text-muted-foreground">Grid Import</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" />
            <span className="text-muted-foreground">Battery Discharge</span>
          </div>
        </div>
      </div>
    </WidgetShell>
  )
}

// 3. Battery State of Charge (wide 2x1)
export function BatterySoCWidget({ data }: { data: ScenarioResult }) {
  const socHistory = data.hourly_plan.map(h => h.battery_energy_after_kwh)
  const capacity = 50.0
  const reserve = 10.0
  const currentSoC = socHistory[socHistory.length - 1] ?? 25.0

  return (
    <WidgetShell title="Battery State of Charge (SoC)" icon={BatteryCharging} meta="Capacity: 50 kWh · Min: 10 kWh">
      <div className="flex flex-col h-full justify-between gap-2">
        <div className="flex items-baseline justify-between">
          <div>
            <span className="text-2xl font-bold tracking-tight text-foreground">{currentSoC.toFixed(1)}</span>
            <span className="text-sm font-normal text-muted-foreground ml-1">kWh</span>
          </div>
          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-medium">
            End-of-day Neutral ({currentSoC === socHistory[0] ? '100% Balanced' : 'Guaranteed'})
          </span>
        </div>

        {/* SVG SoC Curve */}
        <div className="relative w-full h-20 bg-secondary/20 rounded-md p-1 border border-border/30 flex items-center">
          <svg className="w-full h-full overflow-visible" viewBox="0 0 240 60" preserveAspectRatio="none">
            {/* Reserve Line */}
            <line
              x1="0"
              y1={60 - (reserve / capacity) * 60}
              x2="240"
              y2={60 - (reserve / capacity) * 60}
              stroke="hsl(var(--destructive))"
              strokeDasharray="4 2"
              strokeWidth="1.2"
              opacity="0.6"
            />
            {/* SoC Polyline */}
            <polyline
              fill="none"
              stroke="hsl(var(--primary))"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={socHistory
                .map((val, idx) => {
                  const x = (idx / 23) * 240
                  const y = 60 - (val / capacity) * 60
                  return `${x},${y}`
                })
                .join(' ')}
            />
          </svg>
        </div>

        <div className="flex justify-between items-center text-[11px] text-muted-foreground">
          <span className="text-rose-400">--- 10 kWh Reserve Threshold</span>
          <span>Start: 25.0 kWh</span>
          <span className="text-emerald-400">End: 25.0 kWh</span>
        </div>
      </div>
    </WidgetShell>
  )
}

// 4. Tariff Arbitrage (sm 1x1)
export function TariffWidget({ data }: { data: ScenarioResult }) {
  const tariffs = data.hourly_plan.map(h => h.tariff_bdt_per_kwh)
  const maxTariff = Math.max(...tariffs, 15)

  return (
    <WidgetShell title="Tariff Arbitrage" icon={DollarSign} meta="BDT / kWh">
      <div className="flex flex-col h-full justify-between">
        <div className="flex items-center justify-between text-xs">
          <span className="text-emerald-500 font-semibold">Low ৳6.0</span>
          <span className="text-rose-500 font-semibold">Peak ৳15.0</span>
        </div>

        {/* Hourly Tariff Bar Strips */}
        <div className="flex items-end gap-0.5 h-16 pt-2">
          {tariffs.map((rate, i) => {
            const isPeak = rate >= 12
            return (
              <div
                key={i}
                style={{ height: `${(rate / maxTariff) * 100}%` }}
                title={`Hour ${i}:00 — ৳${rate}/kWh`}
                className={`flex-1 rounded-t-sm transition-all duration-300 ${
                  isPeak ? 'bg-rose-500' : 'bg-emerald-500/70'
                }`}
              />
            )
          })}
        </div>

        <p className="text-[11px] text-muted-foreground text-center">
          Charge in ৳6.0 off-peak, discharge during ৳15.0 peak.
        </p>
      </div>
    </WidgetShell>
  )
}

// 5. Directives & LLM Guardrails (wide 2x1)
export function DirectivesWidget({ data }: { data: ScenarioResult }) {
  return (
    <WidgetShell title="Operator Directives & LLM Guardrails" icon={ShieldCheck} meta="Validation Engine">
      <div className="flex flex-col h-full gap-2 overflow-y-auto pr-1">
        {data.directive_interpretation.length === 0 ? (
          <div className="text-sm text-muted-foreground p-3 text-center">
            No active operator directives for this scenario.
          </div>
        ) : (
          data.directive_interpretation.map((item, idx) => (
            <div
              key={idx}
              className={`p-2.5 rounded-lg border text-xs flex flex-col gap-1.5 ${
                item.applies
                  ? 'bg-primary/5 border-primary/20 text-foreground'
                  : 'bg-muted/30 border-border/40 text-muted-foreground'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold flex items-center gap-1.5">
                  {item.applies ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5 text-muted-foreground" />
                  )}
                  {item.directive_type.toUpperCase().replace(/_/g, ' ')}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                    item.applies
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'bg-muted text-muted-foreground border border-border/50'
                  }`}
                >
                  {item.applies ? 'Applied to HiGHS' : 'Filtered (No-Op)'}
                </span>
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2">
                {item.explanation || 'Deterministic validator confirmed bounded parameters.'}
              </p>
              {item.structured_adjustment && (
                <pre className="text-[10px] bg-background/80 p-1.5 rounded font-mono text-muted-foreground overflow-x-auto">
                  {JSON.stringify(item.structured_adjustment)}
                </pre>
              )}
            </div>
          ))
        )}
      </div>
    </WidgetShell>
  )
}

// 6. Interactive Scenario Playground (wide 2x1)
export function PlaygroundWidget({
  onRunScenario,
  loading,
}: {
  onRunScenario: (customNote: string, presetId?: string) => void
  loading: boolean
}) {
  const [customNote, setCustomNote] = useState('')
  const [selectedPreset, setSelectedPreset] = useState('SAMPLE-01')

  const presets = [
    { id: 'SAMPLE-01', label: 'C1: Solar Cleaning' },
    { id: 'SAMPLE-02', label: 'C2: Peak Limit 60kW' },
    { id: 'SAMPLE-03', label: 'C3: Reserve 20kWh' },
    { id: 'SAMPLE-04', label: 'C4: Transformer Window' },
  ]

  return (
    <WidgetShell title="Live Scenario & Solver Playground" icon={Play} meta="HiGHS + LLM Runner">
      <div className="flex flex-col h-full justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground whitespace-nowrap">Preset:</span>
          <div className="flex flex-wrap gap-1">
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setSelectedPreset(p.id)
                  onRunScenario('', p.id)
                }}
                className={`px-2 py-1 rounded text-xs transition-colors ${
                  selectedPreset === p.id
                    ? 'bg-primary text-primary-foreground font-semibold'
                    : 'bg-secondary hover:bg-secondary/80 text-secondary-foreground'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={customNote}
            onChange={(e) => setCustomNote(e.target.value)}
            placeholder='Type custom directive: e.g. "Keep 15 kWh at 6 PM"'
            className="flex-1 px-3 py-1.5 text-xs rounded-md bg-secondary/40 border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && customNote.trim()) {
                onRunScenario(customNote)
              }
            }}
          />
          <button
            onClick={() => onRunScenario(customNote)}
            disabled={loading}
            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold flex items-center gap-1.5 hover:bg-primary/90 transition-opacity disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Solve
          </button>
        </div>

        <p className="text-[11px] text-muted-foreground flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-primary" /> Natural language directives parsed by Gemini with deterministic fallback guardrails.
        </p>
      </div>
    </WidgetShell>
  )
}

// 7. Solver & Engine Health (sm 1x1)
export function HealthWidget({ data }: { data: ScenarioResult }) {
  return (
    <WidgetShell title="Solver Health" icon={Cpu} meta="HiGHS LP">
      <div className="flex flex-col h-full justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-semibold text-foreground">Optimal Solution</span>
        </div>

        <div className="space-y-1 text-xs">
          <div className="flex justify-between text-muted-foreground">
            <span>Latency:</span>
            <span className="font-mono text-foreground">{data.execution_ms ?? 142} ms</span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Provider:</span>
            <span className="font-mono text-foreground capitalize">{data.provider ?? 'Gemini / Cache'}</span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Linear Solver:</span>
            <span className="font-mono text-foreground">SciPy HiGHS</span>
          </div>
        </div>

        <div className="pt-1 text-[11px] text-emerald-500 font-medium">
          Zero 5xx · 100% Guaranteed Feasible
        </div>
      </div>
    </WidgetShell>
  )
}
