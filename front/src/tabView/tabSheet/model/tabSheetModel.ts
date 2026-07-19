import type { TabViewData } from '../../model/types'
import type { TabSheetData } from './types'

export function getTabSheetData(tab: TabViewData): TabSheetData {
  return { section: tab.section }
}
