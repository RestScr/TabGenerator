import { homePageConfig } from '../../config/appConfig'
import { user } from '../../header/model'
import { getFiltersPanelData } from '../filtersPanel/api/filtersPanelApi'
import { getSearchPanelData } from '../searchPanel/api/searchPanelApi'
import { getSongsCatalogData } from '../songsCatalog/api/songsCatalogApi'
import type { HomePageData } from '../model/homePageTypes'

export function getHomePageData(): HomePageData {
  const filtersPanel = getFiltersPanelData()
  const searchPanel = getSearchPanelData()
  const songsCatalog = getSongsCatalogData()

  return {
    user,
    filters: filtersPanel.filters,
    sidebarLinks: filtersPanel.sidebarLinks,
    genres: searchPanel.genres,
    tabs: songsCatalog.tabs,
    totalResults: homePageConfig.totalResults,
    sortLabel: homePageConfig.sortLabel,
  }
}
