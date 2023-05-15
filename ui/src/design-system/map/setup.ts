import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import pin from './pin.svg'

export const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

export const TILE_LAYER_URL =
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

export const DEFAULT_ZOOM = 13

export const MIN_ZOOM = 2

export const MAX_BOUNDS = new L.LatLngBounds([-90, -180], [90, 180])

const DefaultIcon = L.icon({
  iconUrl: pin,
  iconSize: [27, 32],
  iconAnchor: [27 / 2, 32],
})

export const setup = () => {
  L.Marker.prototype.options.icon = DefaultIcon
}
