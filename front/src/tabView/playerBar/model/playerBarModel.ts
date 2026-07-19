import type { TabViewData } from '../../model/types'
import type { PlayerBarData } from './types'

export function getPlayerBarData(tab: TabViewData): PlayerBarData {
  return tab.player
}
