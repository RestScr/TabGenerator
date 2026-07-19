import { filterGroups, sidebarLinks } from '../model/filtersPanelModel'
import type { FilterGroup, SidebarLink } from '../model/types'

export type FiltersPanelData = {
  filters: FilterGroup[]
  sidebarLinks: SidebarLink[]
}

export function getFiltersPanelData(): FiltersPanelData {
  return {
    filters: filterGroups,
    sidebarLinks,
  }
}
