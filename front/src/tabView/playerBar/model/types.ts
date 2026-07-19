export type PlayerControl = {
  id: string
  label: string
  value?: string
  active?: boolean
}

export type PlayerBarData = {
  currentTime: string
  duration: string
  controls: PlayerControl[]
}
