export type TabArtwork = 'mist' | 'dark' | 'warm' | 'wine'

export type Tab = {
  id: string
  title: string
  artist: string
  genre: string
  tabType: string
  meta: string
  difficulty: string
  rating: string
  views: string
  badge: string
  artwork: TabArtwork
  featured: boolean
}
