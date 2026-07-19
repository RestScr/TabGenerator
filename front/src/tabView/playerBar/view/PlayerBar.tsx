import { useState } from 'react'
import type { PlayerBarData } from '../model/types'
import './PlayerBar.css'

type PlayerBarProps = PlayerBarData & {
  isPlaying: boolean
  onTogglePlay: () => void
}

export function PlayerBar({ currentTime, duration, controls, isPlaying, onTogglePlay }: PlayerBarProps) {
  const [activeControls, setActiveControls] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      controls.flatMap((control) => (typeof control.active === 'boolean' ? [[control.id, control.active]] : [])),
    ),
  )

  const toggleControl = (id: string) => {
    setActiveControls((current) => ({ ...current, [id]: !current[id] }))
  }

  return (
    <footer className="player-bar">
      <div className="transport-controls">
        <button type="button" aria-label="Назад">|‹</button>
        <button
          className="play-button"
          type="button"
          aria-label={isPlaying ? 'Пауза' : 'Играть'}
          aria-pressed={isPlaying}
          onClick={onTogglePlay}
        >
          {isPlaying ? 'Ⅱ' : '▶'}
        </button>
        <button type="button" aria-label="Вперед">›|</button>
      </div>

      <div className="player-time">{currentTime} / {duration}</div>

      <div className="player-options">
        {controls.map((control) => (
          <div className="player-option" key={control.id}>
            <span>{control.label}</span>
            {control.value && <strong>{control.value}</strong>}
            {typeof control.active === 'boolean' && (
              <button
                className={activeControls[control.id] ? 'toggle active' : 'toggle'}
                type="button"
                aria-label={control.label}
                aria-pressed={activeControls[control.id]}
                onClick={() => toggleControl(control.id)}
              ></button>
            )}
          </div>
        ))}
      </div>
    </footer>
  )
}
