import type { CSSProperties } from 'react'
import type { TabSheetData } from '../model/types'
import './TabSheet.css'

type TabSheetProps = TabSheetData & {
  activeNoteIds: Set<string>
  playedNoteIds: Set<string>
}

export function TabSheet({ activeNoteIds, playedNoteIds, section }: TabSheetProps) {
  return (
    <section className="tab-sheet" aria-label="Табулатура без ладов">
      <div className="tab-section-divider" aria-hidden="true"></div>

      <div className="tab-grid">
        <div className="tab-string-labels" aria-hidden="true">
          {section.strings.map((stringName) => (
            <span key={stringName}>{stringName}</span>
          ))}
        </div>

        <div className="tab-measures">
          {section.measures.map((measure) => (
            <article className="tab-measure" key={measure.id}>
              <div className="measure-meta">
                <span className="measure-chord">{measure.chord}</span>
                <span className="measure-annotation">{measure.annotation}</span>
              </div>
              <div className="measure-lines">
                {section.strings.map((stringName) => (
                  <span key={stringName}></span>
                ))}
                {measure.notes.map((note) => (
                  <span
                    className={`tab-note${playedNoteIds.has(note.id) ? ' played' : ''}${activeNoteIds.has(note.id) ? ' active' : ''}`}
                    key={note.id}
                    style={{
                      '--note-position': `${note.position * 100}%`,
                      '--note-row': note.stringIndex,
                    } as CSSProperties}
                  >
                    {note.fret}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
