import * as L from 'leaflet'
import icon from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, TileLayer } from 'react-leaflet'
import { ATTRIBUTION, TILE_LAYER_URL } from './constants'
import styles from './styles.module.scss'

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
})
L.Marker.prototype.options.icon = DefaultIcon

export const Map = ({
  center,
  markerPosition,
  markerDraggable,
  onMarkerPositionChange,
}: {
  center: L.LatLng
  markerPosition?: L.LatLng
  markerDraggable?: boolean
  onMarkerPositionChange?: (markerPosition: L.LatLng) => void
}) => {
  const mapRef = useRef<L.Map>(null)
  const markerRef = useRef<L.Marker>(null)

  const eventHandlers = useMemo(
    () => ({
      dragend() {
        const marker = markerRef.current
        if (marker) {
          const updatedMarkerPosition = marker.getLatLng()
          onMarkerPositionChange?.(updatedMarkerPosition)
        }
      },
    }),
    []
  )

  // Center map when marker position is updated
  useEffect(() => {
    const map = mapRef.current
    if (map) {
      map.setView(center, map.getZoom())
    }
  }, [markerPosition])

  return (
    <div className={styles.wrapper}>
      <MapContainer
        center={center}
        className={styles.mapContainer}
        ref={mapRef}
        scrollWheelZoom={false}
        zoom={13}
      >
        <TileLayer attribution={ATTRIBUTION} url={TILE_LAYER_URL} />
        {markerPosition && (
          <Marker
            draggable={markerDraggable}
            eventHandlers={eventHandlers}
            position={markerPosition}
            ref={markerRef}
          />
        )}
      </MapContainer>
    </div>
  )
}

export { LatLng as MarkerPosition } from 'leaflet'
