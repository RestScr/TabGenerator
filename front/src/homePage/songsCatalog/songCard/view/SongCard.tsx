import type { Tab } from '../../model/types'
import './SongCard.css'

type TabProps = {
  tab: Tab
}

type SongCardProps = TabProps & {
  isFavorite: boolean
  onOpenTab: () => void
  onToggleFavorite: () => void
}

function BadgeArt({ tab }: TabProps) {
  return (
    <div className={`badge-art ${tab.artwork}`} aria-hidden="true">
      {tab.badge === 'angle' && <span className="line-angle"></span>}
      {tab.badge === 'slash' && <span className="line-slash"></span>}
      {tab.badge === 'circle' && <span className="circle-art"></span>}
      {tab.badge === 'mark' && <span className="mark-art"></span>}
      {!['angle', 'slash', 'circle', 'mark'].includes(tab.badge) && (
        <span className="badge-text">{tab.badge}</span>
      )}
    </div>
  )
}

export function SongCard({ isFavorite, onOpenTab, onToggleFavorite, tab }: SongCardProps) {
  return (
    <article className="tab-card" aria-labelledby={`tab-title-${tab.id}`}>
      {tab.featured && <span className="featured-star" aria-hidden="true">✦</span>}
      <BadgeArt tab={tab} />

      <div className="tab-info">
        <h3 id={`tab-title-${tab.id}`}>{tab.title}</h3>
        <p>{tab.artist}</p>
        <div className="tab-meta">
          <span>🎸 {tab.meta}</span>
          <span>{tab.difficulty}</span>
        </div>
      </div>

      <div className="rating">
        <strong>★ {tab.rating}</strong>
        <span>{tab.views}</span>
      </div>

      <button className="open-tab" type="button" onClick={onOpenTab}>
        ▷ Открыть таб
      </button>

      <button
        className={isFavorite ? 'favorite active' : 'favorite'}
        type="button"
        aria-label={isFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}
        aria-pressed={isFavorite}
        onClick={onToggleFavorite}
      >
        {isFavorite ? '♥' : '♡'}
      </button>
    </article>
  )
}
