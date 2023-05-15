import * as L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import { MinimapControl } from './minimap-control'
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
  markers,
}: {
  markers: { position: L.LatLng; popupContent?: JSX.Element }[]
}) => {
  const mapRef = useRef<L.Map>(null)

  const bounds = useMemo(() => {
    const _bounds = new L.LatLngBounds([])
    markers.forEach((marker) => _bounds.extend(marker.position))

    return _bounds.pad(0.1)
  }, [markers])

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
        {markers.map((marker, index) => (
          <Marker
            key={index}
            position={marker.position}
            interactive={!!marker.popupContent}
          >
            {marker.popupContent ? (
              <Popup offset={[0, -32]}>{marker.popupContent}</Popup>
            ) : null}
          </Marker>
        ))}
        <MinimapControl />
      </MapContainer>
    </div>
  )
}

export { LatLng as MarkerPosition } from 'leaflet'
