import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import * as L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import {
  ATTRIBUTION,
  MAX_BOUNDS,
  MIN_ZOOM,
  TILE_LAYER_URL,
  setup,
} from '../config'
import { MinimapControl } from '../minimap-control'
import styles from '../styles.module.scss'
import { MarkerPosition } from '../types'

setup()

export const MultiMarkerMap = ({
  markers,
  isLoading,
}: {
  markers: { position: MarkerPosition; popupContent?: JSX.Element }[]
  isLoading?: boolean
}) => {
  const mapRef = useRef<L.Map>(null)

  const bounds = useMemo(() => {
    if (markers.length) {
      const _bounds = new L.LatLngBounds([])
      markers.forEach((marker) => _bounds.extend(marker.position))

      return _bounds.pad(0.1)
    } else {
      return MAX_BOUNDS
    }
  }, [markers])

  useEffect(() => {
    requestAnimationFrame(() => {
      mapRef.current?.fitBounds(bounds)
    })
  }, [mapRef, bounds])

  if (isLoading) {
    return (
      <div className={styles.mapContainer}>
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <MapContainer
      center={bounds.getCenter()}
      className={styles.mapContainer}
      maxBounds={MAX_BOUNDS}
      minZoom={MIN_ZOOM}
      ref={mapRef}
      scrollWheelZoom
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
  )
}
