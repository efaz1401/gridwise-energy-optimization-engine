export interface BatteryConfig {
  capacity_kwh: number
  initial_energy_kwh: number
  minimum_energy_kwh: number
  max_charge_kwh_per_hour: number
  max_discharge_kwh_per_hour: number
}

export interface HourInput {
  hour: number
  demand_kwh: number
  solar_kwh: number
  tariff_bdt_per_kwh: number
}

export interface ScenarioInput {
  scenario_id: string
  operator_notes: string[]
  hours: HourInput[]
  battery: BatteryConfig
}

export const BASE_HOURS: HourInput[] = [
  { hour: 0, demand_kwh: 90, solar_kwh: 0, tariff_bdt_per_kwh: 6 },
  { hour: 1, demand_kwh: 85, solar_kwh: 0, tariff_bdt_per_kwh: 6 },
  { hour: 2, demand_kwh: 80, solar_kwh: 0, tariff_bdt_per_kwh: 5 },
  { hour: 3, demand_kwh: 80, solar_kwh: 0, tariff_bdt_per_kwh: 5 },
  { hour: 4, demand_kwh: 85, solar_kwh: 0, tariff_bdt_per_kwh: 5 },
  { hour: 5, demand_kwh: 95, solar_kwh: 0, tariff_bdt_per_kwh: 6 },
  { hour: 6, demand_kwh: 110, solar_kwh: 5, tariff_bdt_per_kwh: 8 },
  { hour: 7, demand_kwh: 130, solar_kwh: 20, tariff_bdt_per_kwh: 10 },
  { hour: 8, demand_kwh: 150, solar_kwh: 50, tariff_bdt_per_kwh: 12 },
  { hour: 9, demand_kwh: 165, solar_kwh: 90, tariff_bdt_per_kwh: 14 },
  { hour: 10, demand_kwh: 175, solar_kwh: 130, tariff_bdt_per_kwh: 16 },
  { hour: 11, demand_kwh: 180, solar_kwh: 160, tariff_bdt_per_kwh: 16 },
  { hour: 12, demand_kwh: 185, solar_kwh: 180, tariff_bdt_per_kwh: 15 },
  { hour: 13, demand_kwh: 180, solar_kwh: 170, tariff_bdt_per_kwh: 14 },
  { hour: 14, demand_kwh: 170, solar_kwh: 140, tariff_bdt_per_kwh: 13 },
  { hour: 15, demand_kwh: 165, solar_kwh: 90, tariff_bdt_per_kwh: 14 },
  { hour: 16, demand_kwh: 170, solar_kwh: 45, tariff_bdt_per_kwh: 18 },
  { hour: 17, demand_kwh: 185, solar_kwh: 10, tariff_bdt_per_kwh: 22 },
  { hour: 18, demand_kwh: 205, solar_kwh: 0, tariff_bdt_per_kwh: 28 },
  { hour: 19, demand_kwh: 215, solar_kwh: 0, tariff_bdt_per_kwh: 30 },
  { hour: 20, demand_kwh: 205, solar_kwh: 0, tariff_bdt_per_kwh: 26 },
  { hour: 21, demand_kwh: 175, solar_kwh: 0, tariff_bdt_per_kwh: 18 },
  { hour: 22, demand_kwh: 135, solar_kwh: 0, tariff_bdt_per_kwh: 10 },
  { hour: 23, demand_kwh: 105, solar_kwh: 0, tariff_bdt_per_kwh: 7 },
]

export const BASE_BATTERY: BatteryConfig = {
  capacity_kwh: 220,
  initial_energy_kwh: 110,
  minimum_energy_kwh: 40,
  max_charge_kwh_per_hour: 50,
  max_discharge_kwh_per_hour: 50,
}

export const PRESET_SCENARIOS: Record<string, ScenarioInput> = {
  'SAMPLE-01': {
    scenario_id: 'SAMPLE-01',
    operator_notes: [
      'Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.',
      "The sports office moved next month's registration deadline.",
    ],
    hours: BASE_HOURS,
    battery: BASE_BATTERY,
  },
  'SAMPLE-02': {
    scenario_id: 'SAMPLE-02',
    operator_notes: [
      'Cap grid import at 60 kW between 6 PM and 9 PM due to feeder line congestion.',
    ],
    hours: BASE_HOURS,
    battery: BASE_BATTERY,
  },
  'SAMPLE-03': {
    scenario_id: 'SAMPLE-03',
    operator_notes: [
      'Keep at least 60 kWh battery reserve between 5 PM and 10 PM for critical lab backup.',
    ],
    hours: BASE_HOURS,
    battery: BASE_BATTERY,
  },
  'SAMPLE-04': {
    scenario_id: 'SAMPLE-04',
    operator_notes: [
      'Do not charge battery from grid between 8 AM and 11 AM due to transformer maintenance.',
    ],
    hours: BASE_HOURS,
    battery: BASE_BATTERY,
  },
}

// Initial offline fallback result
export const DEFAULT_RESULT = {
  scenario_id: 'SAMPLE-01',
  total_grid_kwh: 2240.0,
  total_cost_bdt: 34150.0,
  peak_grid_kwh: 175.0,
  plan_summary: 'Applied solar_reduction; ignored 1 unrelated note(s); charged in low-tariff hours and discharged into peak hours.',
  directive_interpretation: [
    {
      note_index: 0,
      applies: true,
      directive_type: 'solar_reduction',
      structured_adjustment: { hours: [12, 13], factor: 0.25 },
      explanation: 'Usable solar scaled to 25% from 12:00 to 14:00 during scheduled cleaning.',
    },
    {
      note_index: 1,
      applies: false,
      directive_type: 'no_op',
      structured_adjustment: null,
      explanation: 'Sports registration deadline is irrelevant to energy dispatch.',
    },
  ],
  hourly_plan: BASE_HOURS.map((h, i) => {
    const isSolarWindow = i >= 6 && i <= 17
    const solarGen = isSolarWindow ? h.solar_kwh : 0
    const cleaningFactor = (i === 12 || i === 13) ? 0.25 : 1.0
    const effectiveSolar = solarGen * cleaningFactor
    const solarUsed = Math.min(effectiveSolar, h.demand_kwh)
    const isOffPeak = h.tariff_bdt_per_kwh <= 6
    const isPeak = h.tariff_bdt_per_kwh >= 20
    const batteryAction: 'charge' | 'discharge' | 'idle' = isOffPeak ? 'charge' : isPeak ? 'discharge' : 'idle'
    const batteryKw = batteryAction === 'charge' ? 30 : batteryAction === 'discharge' ? 40 : 0
    const gridKw = Math.max(0, h.demand_kwh - solarUsed + (batteryAction === 'charge' ? batteryKw : -batteryKw))
    const soc = 110 + (i <= 5 ? i * 15 : i >= 18 ? 160 - (i - 17) * 15 : 160)

    return {
      hour: h.hour,
      demand_kwh: h.demand_kwh,
      solar_kwh: h.solar_kwh,
      effective_solar_kwh: effectiveSolar,
      tariff_bdt_per_kwh: h.tariff_bdt_per_kwh,
      grid_kwh: Math.round(gridKw * 10) / 10,
      solar_used_kwh: Math.round(solarUsed * 10) / 10,
      battery_action: batteryAction,
      battery_kwh: batteryKw,
      battery_energy_after_kwh: Math.min(220, Math.max(40, Math.round(soc))),
    }
  }),
  execution_ms: 142,
  provider: 'Gemini 3 Flash Preview',
}
