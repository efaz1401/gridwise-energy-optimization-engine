import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  Layers,
  Moon,
  RotateCcw,
  Sparkles,
  Sun,
  Zap,
} from 'lucide-react'
import DraggableWidgetGrid, {
  type WidgetItem,
  type WidgetSize,
} from '@/components/ui/draggable-widget-grid'
import {
  BatterySoCWidget,
  DirectivesWidget,
  DispatchTimelineWidget,
  HealthWidget,
  KpiWidget,
  PlaygroundWidget,
  TariffWidget,
  type ScenarioResult,
} from '@/components/widgets/gridwise-widgets'
import {
  BASE_BATTERY,
  BASE_HOURS,
  DEFAULT_RESULT,
  PRESET_SCENARIOS,
  type ScenarioInput,
} from '@/presets'

const INITIAL_WIDGETS: WidgetItem[] = [
  { id: 'kpi', size: 'wide', label: 'Energy KPIs & Cost' },
  { id: 'playground', size: 'wide', label: 'Live Scenario & Solver Playground' },
  { id: 'dispatch', size: 'lg', label: '24h Energy Dispatch Timeline' },
  { id: 'battery', size: 'wide', label: 'Battery State of Charge' },
  { id: 'tariffs', size: 'sm', label: 'Tariff Arbitrage' },
  { id: 'health', size: 'sm', label: 'Solver & Engine Health' },
  { id: 'directives', size: 'wide', label: 'Directives & LLM Guardrails' },
]

export default function App() {
  const [widgets, setWidgets] = useState<WidgetItem[]>(INITIAL_WIDGETS)
  const [data, setData] = useState<ScenarioResult>(DEFAULT_RESULT)
  const [loading, setLoading] = useState<boolean>(false)
  const [darkMode, setDarkMode] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Sync dark mode class with HTML element
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  // Solver execution function
  const runScenario = useCallback(
    async (customNote?: string, presetId = 'SAMPLE-01') => {
      setLoading(true)
      setErrorMsg(null)
      const startTime = performance.now()

      try {
        let payload: ScenarioInput
        if (customNote && customNote.trim()) {
          payload = {
            scenario_id: `CUSTOM-${Date.now().toString().slice(-4)}`,
            operator_notes: [customNote.trim()],
            hours: BASE_HOURS,
            battery: BASE_BATTERY,
          }
        } else {
          payload = PRESET_SCENARIOS[presetId] || PRESET_SCENARIOS['SAMPLE-01']
        }

        const res = await fetch('http://127.0.0.1:8000/optimize-energy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })

        if (!res.ok) {
          throw new Error(`API responded with HTTP ${res.status}`)
        }

        const json = await res.json()
        const elapsed = Math.round(performance.now() - startTime)

        // Merge response with timing & hours
        const enrichedPlan = json.hourly_plan.map((h: any, idx: number) => ({
          ...h,
          demand_kwh: BASE_HOURS[idx]?.demand_kwh ?? 100,
          solar_kwh: BASE_HOURS[idx]?.solar_kwh ?? 0,
          tariff_bdt_per_kwh: BASE_HOURS[idx]?.tariff_bdt_per_kwh ?? 10,
        }))

        setData({
          ...json,
          hourly_plan: enrichedPlan,
          execution_ms: elapsed,
          provider: 'Gemini 3 Flash Preview',
        })
      } catch (err: any) {
        console.warn('Backend call failed, using heuristic preview:', err)
        setErrorMsg('Note: Backend offline or busy — displaying interactive preview.')
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  // Initial load check
  useEffect(() => {
    runScenario()
  }, [runScenario])

  // Widget rendering dispatcher
  const renderWidget = (item: WidgetItem, _size: WidgetSize) => {
    switch (item.id) {
      case 'kpi':
        return <KpiWidget data={data} />
      case 'dispatch':
        return <DispatchTimelineWidget data={data} />
      case 'battery':
        return <BatterySoCWidget data={data} />
      case 'tariffs':
        return <TariffWidget data={data} />
      case 'directives':
        return <DirectivesWidget data={data} />
      case 'playground':
        return <PlaygroundWidget onRunScenario={runScenario} loading={loading} />
      case 'health':
        return <HealthWidget data={data} />
      default:
        return (
          <div className="p-4 text-xs text-muted-foreground">Widget: {item.id}</div>
        )
    }
  }

  return (
    <main className="min-h-screen bg-background text-foreground selection:bg-primary/20 px-4 py-8 sm:px-8">
      <div className="max-w-[1240px] mx-auto flex flex-col gap-6">
        {/* Navigation Bar */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-primary-foreground shadow-sm shadow-primary/25">
              <Zap className="w-5 h-5 fill-current" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-foreground">
                  GridWise
                </h1>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  HiGHS Solved
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Microgrid 24h Energy Optimization & LLM Guardrail Dispatcher
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={() => setWidgets([...INITIAL_WIDGETS])}
              className="px-3 py-1.5 rounded-lg border border-border bg-card text-xs font-medium hover:bg-accent transition-colors flex items-center gap-1.5 shadow-sm"
              title="Reset widgets to initial layout"
            >
              <RotateCcw className="w-3.5 h-3.5 text-muted-foreground" />
              Reset Layout
            </button>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="p-2 rounded-lg border border-border bg-card text-xs hover:bg-accent transition-colors shadow-sm"
              title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {darkMode ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-muted-foreground" />
              )}
            </button>
          </div>
        </header>

        {/* Status / Notice Pill */}
        {errorMsg && (
          <div className="px-3 py-2 rounded-md bg-amber-500/10 border border-amber-500/20 text-xs text-amber-600 dark:text-amber-400 flex items-center justify-between">
            <span>{errorMsg}</span>
            <button
              onClick={() => runScenario()}
              className="underline font-semibold ml-2"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Instructions strip */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-primary" />
            <span className="hidden sm:inline">
              Drag widgets freely to customize your layout. On mobile, press & hold to drag. Alt + Arrow keys for keyboard rearrangement.
            </span>
            <span className="sm:hidden">
              Press and hold to drag and rearrange widgets.
            </span>
          </p>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-foreground">
              {data.scenario_id}
            </span>
          </div>
        </div>

        {/* Draggable Widget Grid */}
        <section aria-label="GridWise Energy Observability Grid">
          <DraggableWidgetGrid
            items={widgets}
            onChange={setWidgets}
            renderItem={renderWidget}
            maxColumns={4}
            cellSize={260}
            gap={14}
            radius={20}
          />
        </section>

        {/* Footer Summary */}
        <footer className="pt-4 pb-8 border-t border-border/60 text-xs text-muted-foreground flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>
            {data.plan_summary ||
              'Charged in low-tariff hours and discharged into peak hours while respecting bounds.'}
          </p>
          <span className="text-[11px] text-muted-foreground font-mono">
            BUP CSE Fest 2026 · GridWise Production Release
          </span>
        </footer>
      </div>
    </main>
  )
}
