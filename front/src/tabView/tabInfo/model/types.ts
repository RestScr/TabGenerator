export type TabAction = {
  id: string
  label: string
  icon: string
}

export type TabMetaChip = {
  id: string
  label: string
  value: string
  icon?: string
  options: string[]
}

export type TabInfoData = {
  title: string
  artist: string
  metaChips: TabMetaChip[]
  revisedAt: string
  actions: TabAction[]
}
