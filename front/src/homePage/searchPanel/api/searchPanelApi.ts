import { genres } from '../model/searchPanelModel'

export type SearchPanelData = {
  genres: string[]
}

export function getSearchPanelData(): SearchPanelData {
  return {
    genres,
  }
}
