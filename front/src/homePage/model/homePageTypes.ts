import type { User } from '../../header/model'
import type { FilterGroup, SidebarLink } from '../filtersPanel/model/types'
import type { Tab } from '../songsCatalog/model/types'

export type HomePageData = {
  user: User
  filters: FilterGroup[]
  sidebarLinks: SidebarLink[]
  genres: string[]
  tabs: Tab[]
  totalResults: string
  sortLabel: string
}
