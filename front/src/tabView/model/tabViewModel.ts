import { user } from '../../header/model'
import { parseAsciiTab } from '../tabSheet/model/asciiTabParser'
import type { TabViewData } from './types'

const stairwayIntroAsciiTab = `E |---------------------------|------------0------------0-|---------------------------|-------------0---------|
B |---------0------------0----|----------------------2----|---------0------------0----|-----------------------|
G |------2------------2-------|------2------------2-------|------2------------2-------|-------2---------------|
D |---2------------2----------|---2-----------------------|---2------------2----------|----2------------------|
A |---------------------------|-4-------------------------|-3-------------------------|-----------------------|
C#|-0-------------------------|---------------------------|---------------------------|-----------------------|`

const parsedStairwayIntro = parseAsciiTab(stairwayIntroAsciiTab)
const introChords = ['Am', 'C/G', 'D/F#', 'Fmaj7']

export const tabViewData: TabViewData = {
  user,
  title: 'Stairway to Heaven',
  artist: 'Led Zeppelin',
  metaChips: [
    {
      id: 'tuning',
      label: 'Тюнинг',
      value: 'E B G D A C#',
      icon: '♮',
      options: ['E B G D A C#', 'E B G D A E', 'D A F C G D'],
    },
    {
      id: 'sound',
      label: 'Звук',
      value: 'Clean',
      icon: '♯',
      options: ['Clean', 'Crunch', 'Overdrive'],
    },
  ],
  revisedAt: '15.06.2026',
  actions: [
    { id: 'favorite', label: 'В избранное', icon: '☆' },
    { id: 'download', label: 'Скачать', icon: '↓' },
    { id: 'more', label: 'Еще', icon: '⋮' },
  ],
  section: {
    id: 'intro',
    title: 'Интро',
    tempo: '♩ = 71',
    tempoBpm: 71,
    beatsPerMeasure: 4,
    description: 'Gradual accel. between tempos throughout the song',
    strings: parsedStairwayIntro.strings,
    stringMidi: [64, 59, 55, 50, 45, 37],
    measures: parsedStairwayIntro.measures.map((measure, index) => ({
      ...measure,
      chord: introChords[index],
      annotation: 'let ring ------|',
    })),
  },
  player: {
    currentTime: '0:00',
    duration: '8:02',
    controls: [
      { id: 'speed', label: 'Скорость', value: '100%' },
      { id: 'loop', label: 'Петля', value: 'Выкл', active: true },
      { id: 'metronome', label: 'Метроном', active: false },
      { id: 'solo', label: 'Соло' },
      { id: 'count', label: 'Отсчёт', value: '3' },
      { id: 'scroll', label: 'Прокрутка', active: true },
    ],
  },
}

export const tabViewDataById: Record<string, TabViewData> = {
  stairway: tabViewData,
}
