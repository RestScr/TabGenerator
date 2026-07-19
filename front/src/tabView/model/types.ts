import type { User } from '../../header/model'
import type { TabAction, TabMetaChip } from '../tabInfo/model/types'
import type { TabSection } from '../tabSheet/model/types'
import type { PlayerControl } from '../playerBar/model/types'

export type TabViewData = {
  user: User
  title: string
  artist: string
  metaChips: TabMetaChip[]
  revisedAt: string
  actions: TabAction[]
  section: TabSection
  player: {
    currentTime: string
    duration: string
    controls: PlayerControl[]
  }
}
