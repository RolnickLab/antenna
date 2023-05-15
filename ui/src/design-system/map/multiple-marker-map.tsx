import * as L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, TileLayer } from 'react-leaflet'
import {
  ATTRIBUTION,
  MAX_BOUNDS,
  MIN_ZOOM,
  setup,
  TILE_LAYER_URL,
} from './setup'
import styles from './styles.module.scss'

setup()

export const MultipleMarkerMap = ({
  markerPositions,
}: {
  markerPositions: L.LatLng[]
}) => {
  const mapRef = useRef<L.Map>(null)

  const bounds = useMemo(() => {
    const _bounds = new L.LatLngBounds([])
    markerPositions.forEach((mp) => _bounds.extend(mp))

    return _bounds.pad(0.1)
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
        maxBounds={MAX_BOUNDS}
        minZoom={MIN_ZOOM}
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
