import { MarkerPosition } from 'design-system/map/types'

export interface ServerSearchResult {
  osm_id: number
  display_name: string
  lat: string
  lon: string
}

export interface SearchResult {
  osmId: number
  displayName: string
  position: MarkerPosition
}
