import type { Tab } from '../model/types'
import { getSongCardData } from '../songCard/api/songCardApi'
import { SongCard } from '../songCard/view/SongCard'
import './SongsList.css'

type SongsListProps = {
  tabs: Tab[]
  favoriteIds: Set<string>
  onOpenTab: (tabId: string) => void
  onToggleFavorite: (tabId: string) => void
}

export function SongsList({ favoriteIds, onOpenTab, onToggleFavorite, tabs }: SongsListProps) {
  return (
    <section className="tabs-list" aria-label="Список табов">
      {tabs.map((tab) => (
        <SongCard
          key={tab.id}
          tab={getSongCardData(tab)}
          isFavorite={favoriteIds.has(tab.id)}
          onOpenTab={() => onOpenTab(tab.id)}
          onToggleFavorite={() => onToggleFavorite(tab.id)}
        />
      ))}
    </section>
  )
}
