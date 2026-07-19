import { useMemo, useState } from 'react'
import { Header } from '../../header/view/Header'
import { getHomePageData } from '../api/homePageApi'
import { FiltersSidebar } from '../filtersPanel/view/FiltersSidebar'
import { SearchPanel } from '../searchPanel/view/SearchPanel'
import { SongsList } from '../songsCatalog/view/SongsList'
import './HomePage.css'

type HomePageProps = {
  onOpenTab: (tabId: string) => void
  onHomeClick: () => void
}

export function HomePage({ onHomeClick, onOpenTab }: HomePageProps) {
  const page = getHomePageData()
  const [query, setQuery] = useState('')
  const [selectedGenre, setSelectedGenre] = useState('Все')
  const [sortIndex, setSortIndex] = useState(0)
  const [filterValues, setFilterValues] = useState<Record<string, string>>({})
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set())
  const [activeLink, setActiveLink] = useState<string | undefined>()
  const sortLabels = [page.sortLabel, 'По рейтингу', 'По названию']

  const visibleTabs = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    const activeGenre = selectedGenre !== 'Все'
      ? selectedGenre
      : filterValues.genre === 'Все'
        ? undefined
        : filterValues.genre

    const filteredTabs = page.tabs.filter((tab) => {
      const matchesQuery = !normalizedQuery || `${tab.title} ${tab.artist} ${tab.meta}`.toLocaleLowerCase().includes(normalizedQuery)
      const matchesGenre = !activeGenre || tab.genre === activeGenre
      const matchesInstrument = !filterValues.instrument || tab.meta.includes(filterValues.instrument)
      const matchesDifficulty = !filterValues.difficulty || filterValues.difficulty === 'Все' || tab.difficulty === filterValues.difficulty
      const matchesTabType = !filterValues.tabType || filterValues.tabType === 'Все' || tab.tabType === filterValues.tabType
      const matchesTuning = !filterValues.tuning || tab.meta.includes(filterValues.tuning)
      const matchesFavorites = activeLink !== 'favorites' || favoriteIds.has(tab.id)

      return matchesQuery && matchesGenre && matchesInstrument && matchesDifficulty && matchesTabType && matchesTuning && matchesFavorites
    })

    return [...filteredTabs].sort((left, right) => {
      if (sortIndex === 1) return Number(right.rating) - Number(left.rating)
      if (sortIndex === 2) return left.title.localeCompare(right.title)
      return Number(right.views.replace(/[MK]/, '')) - Number(left.views.replace(/[MK]/, ''))
    })
  }, [activeLink, favoriteIds, filterValues, page.tabs, query, selectedGenre, sortIndex])

  const handleFilterChange = (id: string, value: string) => {
    setFilterValues((current) => ({ ...current, [id]: value }))
    if (id === 'genre') setSelectedGenre(value)
    setActiveLink(undefined)
  }

  const handleGenreChange = (genre: string) => {
    setSelectedGenre(genre)
    setFilterValues((current) => {
      if (genre === 'Все') {
        const next = { ...current }
        delete next.genre
        return next
      }
      return { ...current, genre }
    })
    setActiveLink(undefined)
  }

  const toggleFavorite = (tabId: string) => {
    setFavoriteIds((current) => {
      const next = new Set(current)
      if (next.has(tabId)) next.delete(tabId)
      else next.add(tabId)
      return next
    })
  }

  return (
    <div className="app-shell">
      <Header user={page.user} onLogoClick={onHomeClick} onOpenTab={onOpenTab} showSearch={false} />
      <main className="home-layout">
        <FiltersSidebar
          activeLink={activeLink}
          filters={page.filters}
          links={page.sidebarLinks}
          values={filterValues}
          onFilterChange={handleFilterChange}
          onLinkClick={(id) => setActiveLink((current) => (current === id ? undefined : id))}
        />
        <div className="content-area">
          <div className="ambient-circle"></div>
          <SearchPanel
            genres={page.genres}
            query={query}
            selectedGenre={selectedGenre}
            sortLabel={sortLabels[sortIndex] ?? page.sortLabel}
            totalResults={visibleTabs.length.toLocaleString('ru-RU')}
            onGenreChange={handleGenreChange}
            onQueryChange={(value) => {
              setQuery(value)
              setActiveLink(undefined)
            }}
            onSortChange={() => setSortIndex((current) => (current + 1) % sortLabels.length)}
          />
          <SongsList
            favoriteIds={favoriteIds}
            tabs={visibleTabs}
            onOpenTab={onOpenTab}
            onToggleFavorite={toggleFavorite}
          />
        </div>
      </main>
    </div>
  )
}
