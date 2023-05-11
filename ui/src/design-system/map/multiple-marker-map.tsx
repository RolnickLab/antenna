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

export const MultipleMarkerMap = ({
  markerPositions,
}: {
  markerPositions: L.LatLng[]
}) => {
  const mapRef = useRef<L.Map>(null)

  const bounds = useMemo(() => {
    const _bounds = new L.LatLngBounds([])
    markerPositions.forEach((mp) => _bounds.extend(mp))

    return _bounds
  }, [markerPositions])

  useEffect(() => {
    requestAnimationFrame(() => {
      mapRef.current?.fitBounds(bounds)
    })
  }, [mapRef, bounds])

  return (
    <div className={styles.wrapper}>
      <MapContainer
        center={bounds.getCenter()}
        className={styles.mapContainer}
        ref={mapRef}
        scrollWheelZoom={false}
      >
        <TileLayer attribution={ATTRIBUTION} url={TILE_LAYER_URL} />
        {markerPositions.map((markerPosition, index) => (
          <Marker key={index} position={markerPosition} />
        ))}
      </MapContainer>
    </div>
  )
}

export { LatLng as MarkerPosition } from 'leaflet'
