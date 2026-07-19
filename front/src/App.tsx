import { useEffect, useState } from 'react'
import { HomePage } from './homePage/view/HomePage'
import { TabView } from './tabView/view/TabView'
import './App.css'

type AppRoute =
  | { screen: 'home' }
  | { screen: 'tabView'; tabId: string }

function getRoute(): AppRoute {
  const match = window.location.pathname.match(/^\/tab\/([^/]+)$/)
  if (!match) return { screen: 'home' }

  return {
    screen: 'tabView',
    tabId: decodeURIComponent(match[1]),
  }
}

function App() {
  const [route, setRoute] = useState<AppRoute>(getRoute)

  useEffect(() => {
    const handlePopState = () => setRoute(getRoute())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const navigate = (path: string) => {
    window.history.pushState({}, '', path)
    setRoute(getRoute())
  }

  const openHome = () => navigate('/')
  const openTabView = (tabId: string) => navigate(`/tab/${encodeURIComponent(tabId)}`)

  if (route.screen === 'tabView') {
    return <TabView tabId={route.tabId} onHomeClick={openHome} onOpenTab={openTabView} />
  }

  return <HomePage onHomeClick={openHome} onOpenTab={openTabView} />
}

export default App
