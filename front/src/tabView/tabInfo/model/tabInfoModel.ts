import type { TabViewData } from '../../model/types'
import type { TabInfoData } from './types'

export function getTabInfoData(tab: TabViewData): TabInfoData {
  return {
    actions: tab.actions,
    artist: tab.artist,
    metaChips: tab.metaChips,
    revisedAt: tab.revisedAt,
    title: tab.title,
  }
}
