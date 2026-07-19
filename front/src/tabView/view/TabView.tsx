import { useEffect, useState } from 'react'
import { getTabViewData } from '../api/tabViewApi'
import { Header } from '../../header/view/Header'
import { user } from '../../header/model'
import { tabViewData } from '../model/tabViewModel'
import { getPlayerBarData } from '../playerBar/api/playerBarApi'
import { useTabPlayback } from '../playerBar/model/useTabPlayback'
import { PlayerBar } from '../playerBar/view/PlayerBar'
import { getTabInfoData } from '../tabInfo/api/tabInfoApi'
import { TabInfo } from '../tabInfo/view/TabInfo'
import { getTabSheetData } from '../tabSheet/api/tabSheetApi'
import { TabSheet } from '../tabSheet/view/TabSheet'
import './TabView.css'

type TabViewProps = {
  tabId: string
  onHomeClick: () => void
  onOpenTab: (tabId: string) => void
}

export function TabView({ onHomeClick, onOpenTab, tabId }: TabViewProps) {
  const [tab, setTab] = useState<Awaited<ReturnType<typeof getTabViewData>>>()
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let isCurrent = true
    setTab(undefined)
    setError(undefined)

    void getTabViewData(tabId)
      .then((loadedTab) => {
        if (isCurrent) setTab(loadedTab)
      })
      .catch((loadError) => {
        if (isCurrent) setError(loadError instanceof Error ? loadError.message : 'Не удалось открыть таб')
      })

    return () => { isCurrent = false }
  }, [tabId])

  const tabSheet = getTabSheetData(tab ?? tabViewData)
  const playback = useTabPlayback(tabSheet.section)

  if (!tab) {
    return (
      <div className="tab-view-shell">
        <Header user={user} onLogoClick={onHomeClick} onOpenTab={onOpenTab} showSearch />
        <main className="tab-view-state" aria-live="polite">
          <h1>{error ? 'Таб не открыт' : 'Загружаем таб...'}</h1>
          <p>{error || 'Получаем ноты и настройки табулатуры.'}</p>
        </main>
      </div>
    )
  }

  return (
    <div className="tab-view-shell">
      <Header user={tab.user} onLogoClick={onHomeClick} onOpenTab={onOpenTab} showSearch />
      <main className="tab-view-main">
        <TabInfo {...getTabInfoData(tab)} />
        <TabSheet
          {...tabSheet}
          activeNoteIds={playback.activeNoteIds}
          playedNoteIds={playback.playedNoteIds}
        />
      </main>
      <PlayerBar
        {...getPlayerBarData(tab)}
        currentTime={playback.currentTime}
        duration={playback.duration}
        isPlaying={playback.isPlaying}
        onTogglePlay={playback.togglePlayback}
      />
    </div>
  )
}
