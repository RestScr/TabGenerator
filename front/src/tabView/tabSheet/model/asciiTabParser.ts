import type { TabMeasure, TabNote } from './types'

type AsciiTabRow = {
  stringName: string
  measures: string[]
}

export type ParsedAsciiTab = {
  strings: string[]
  measures: TabMeasure[]
}

function parseRow(line: string): AsciiTabRow | undefined {
  const separatorIndex = line.indexOf('|')
  if (separatorIndex === -1) return undefined

  const stringName = line.slice(0, separatorIndex).trim()
  if (!stringName) return undefined

  const measures = line.slice(separatorIndex + 1).split('|')
  if (measures.at(-1) === '') measures.pop()

  return { stringName, measures }
}

function getNotes(segment: string, stringIndex: number, measureIndex: number): TabNote[] {
  const notes: TabNote[] = []
  const maxPosition = Math.max(segment.length - 1, 1)

  for (let column = 0; column < segment.length; column += 1) {
    if (!/\d/.test(segment[column] ?? '')) continue

    const startColumn = column
    let fretText = ''

    while (column < segment.length && /\d/.test(segment[column] ?? '')) {
      fretText += segment[column]
      column += 1
    }

    const rawPosition = startColumn / maxPosition
    const position = Math.min(1, Math.max(0, Math.round(rawPosition * 16) / 16))
    notes.push({
      id: `m${measureIndex + 1}-s${stringIndex + 1}-c${startColumn}`,
      stringIndex,
      fret: Number(fretText),
      position,
    })

    column -= 1
  }

  return notes
}

export function parseAsciiTab(asciiTab: string): ParsedAsciiTab {
  const rows = asciiTab
    .split(/\r?\n/)
    .map((line) => parseRow(line.trimEnd()))
    .filter((row): row is AsciiTabRow => Boolean(row))

  if (rows.length === 0) {
    throw new Error('ASCII tab must contain at least one string row')
  }

  const measureCount = Math.min(...rows.map((row) => row.measures.length))
  if (measureCount === 0) {
    throw new Error('ASCII tab must contain at least one measure')
  }

  return {
    strings: rows.map((row) => row.stringName),
    measures: Array.from({ length: measureCount }, (_, measureIndex) => ({
      id: `m${measureIndex + 1}`,
      number: measureIndex + 1,
      notes: rows.flatMap((row, stringIndex) => getNotes(row.measures[measureIndex] ?? '', stringIndex, measureIndex)),
    })),
  }
}
