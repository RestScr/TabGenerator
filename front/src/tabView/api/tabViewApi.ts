import { apiConfig } from '../../config/apiConfig'
import { parseAsciiTab } from '../tabSheet/model/asciiTabParser'
import { tabViewData, tabViewDataById } from '../model/tabViewModel'
import type { TabViewData } from '../model/types'

type GeneratedTabResponse = {
  id: string
  title: string
  tempo_bpm: number
  ascii_tab: string
  tab_data?: {
    strings: string[]
    note_events?: Array<{
      id: string
      pitch: number
      start: number
      end: number | null
      duration: number
      duration_beats: number
      subdivision: 'whole' | 'half' | 'quarter' | 'eighth' | 'sixteenth'
      tie_start: boolean
      tie_end: boolean
      velocity: number
      string: number
      fret: number
      measure: number
      beat: number
      position: number
      technique: string | null
    }>
    measures: Array<{
      number: number
      notes: Array<{ id: string; string: number; fret: number; position: number }>
    }>
  }
}

const generatedTabIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const defaultStringMidi = [64, 59, 55, 50, 45, 40]
const stringMidiByName: Record<string, number> = { B: 59, G: 55, D: 50, A: 45, 'C#': 37 }

function formatRevisionDate(): string {
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date())
}

function mapGeneratedTab(tab: GeneratedTabResponse): TabViewData {
  const parsedTab = parseAsciiTab(tab.ascii_tab)
  const timedEvents = tab.tab_data?.note_events
  const structuredMeasures = tab.tab_data?.measures?.map((measure, measureIndex) => ({
    id: `m${measure.number}`,
    number: measure.number,
    notes: (timedEvents
      ? timedEvents.filter((event) => event.measure === measure.number)
      : measure.notes.map((note) => ({
        id: note.id,
        pitch: 0,
        start: 0,
        end: null,
        duration: 0,
        velocity: 0,
        string: note.string,
        fret: note.fret,
        measure: measureIndex + 1,
        beat: note.position * 4,
        position: note.position,
        technique: null,
      })))
      .map((note) => ({
        id: note.id,
        stringIndex: note.string,
        fret: note.fret,
        position: note.position,
        pitch: note.pitch,
        start: note.start,
        duration: note.duration,
        durationBeats: 'duration_beats' in note ? note.duration_beats : undefined,
        subdivision: 'subdivision' in note ? note.subdivision : undefined,
        tieStart: 'tie_start' in note ? note.tie_start : undefined,
        tieEnd: 'tie_end' in note ? note.tie_end : undefined,
        velocity: note.velocity,
        technique: note.technique,
      })),
  }))
  const strings = tab.tab_data?.strings ?? parsedTab.strings

  return {
    ...tabViewData,
    title: tab.title,
    artist: 'Загруженный трек',
    revisedAt: formatRevisionDate(),
    section: {
      ...tabViewData.section,
      id: tab.id,
      title: 'Табулатура',
      tempo: `♩ = ${tab.tempo_bpm}`,
      tempoBpm: tab.tempo_bpm,
      description: 'Табулатура создана автоматически из загруженного аудио.',
      strings,
      stringMidi: strings.map((stringName, index) => stringMidiByName[stringName] ?? defaultStringMidi[index] ?? 40),
      measures: structuredMeasures ?? parsedTab.measures,
    },
  }
}

export async function getTabViewData(tabId = 'stairway'): Promise<TabViewData> {
  if (!generatedTabIdPattern.test(tabId)) {
    return tabViewDataById[tabId] ?? tabViewData
  }

  let response = await fetch(`${apiConfig.baseUrl}/tabs/${encodeURIComponent(tabId)}`)
  if (!response.ok && response.status === 404) {
    // Prepared audio tabs are file-backed until tab results are persisted in
    // the database. The job id is also the stable tab id for this route.
    response = await fetch(`${apiConfig.baseUrl}/jobs/${encodeURIComponent(tabId)}/tab`)
  }
  if (!response.ok) throw new Error('Не удалось загрузить готовую табулатуру')
  return mapGeneratedTab(await response.json() as GeneratedTabResponse)
}
