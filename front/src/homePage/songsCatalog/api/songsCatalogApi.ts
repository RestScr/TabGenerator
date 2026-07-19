import { tabs } from '../model/songsCatalogModel'
import type { Tab } from '../model/types'

export type SongsCatalogData = {
  tabs: Tab[]
}

export function getSongsCatalogData(): SongsCatalogData {
  return {
    tabs,
  }
}
