export type TabNote = {
  id: string
  stringIndex: number
  fret: number
  position: number
  pitch?: number
  start?: number
  duration?: number
  durationBeats?: number
  subdivision?: 'whole' | 'half' | 'quarter' | 'eighth' | 'sixteenth'
  tieStart?: boolean
  tieEnd?: boolean
  velocity?: number
  technique?: string | null
}

export type TabMeasure = {
  id: string
  number: number
  chord?: string
  annotation?: string
  notes: TabNote[]
}

export type TabSection = {
  id: string
  title: string
  tempo: string
  tempoBpm: number
  beatsPerMeasure: number
  description: string
  strings: string[]
  stringMidi: number[]
  measures: TabMeasure[]
}

export type TabSheetData = {
  section: TabSection
}
