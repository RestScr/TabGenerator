import { useState } from 'react'
import type { TabInfoData } from '../model/types'
import './TabInfo.css'

type TabInfoProps = TabInfoData

export function TabInfo({ title, artist, metaChips, revisedAt, actions }: TabInfoProps) {
  const [isFavorite, setIsFavorite] = useState(false)
  const [isDownloaded, setIsDownloaded] = useState(false)
  const [isMoreOpen, setIsMoreOpen] = useState(false)
  const [chipValues, setChipValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(metaChips.map((chip) => [chip.id, chip.value])),
  )

  return (
    <section className="tab-info-hero">
      <div className="tab-info-heading-row">
        <div>
          <h1>{title}</h1>
          <p>{artist}</p>
        </div>

        <div className="tab-info-actions">
          {actions.map((action) => (
            <button
              className={`tab-action tab-action-${action.id}${action.id === 'favorite' && isFavorite ? ' active' : ''}`}
              type="button"
              key={action.id}
              aria-label={action.label}
              aria-pressed={action.id === 'favorite' ? isFavorite : undefined}
              onClick={() => {
                if (action.id === 'favorite') setIsFavorite((current) => !current)
                if (action.id === 'download') setIsDownloaded(true)
                if (action.id === 'more') setIsMoreOpen((current) => !current)
              }}
            >
              <span>{action.id === 'favorite' && isFavorite ? '★' : action.icon}</span>
              {action.id === 'download' && <strong>{isDownloaded ? 'Скачано' : action.label}</strong>}
            </button>
          ))}
          {isMoreOpen && <span className="tab-more-menu">Дополнительные действия</span>}
        </div>
      </div>

      <div className="tab-info-meta">
        {metaChips.map((chip) => (
          <label className="tab-info-select" key={chip.id}>
            {chip.icon && <span className="tab-info-select-icon" aria-hidden="true">{chip.icon}</span>}
            <span className="tab-info-select-label">{chip.label}:</span>
            <select
              aria-label={chip.label}
              value={chipValues[chip.id] ?? chip.value}
              onChange={(event) => setChipValues((current) => ({ ...current, [chip.id]: event.target.value }))}
            >
              {chip.options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
            <span className="tab-info-select-chevron" aria-hidden="true"></span>
          </label>
        ))}
        <span className="tab-info-revision">▣ Ревизия от: <b>{revisedAt}</b></span>
      </div>
    </section>
  )
}
