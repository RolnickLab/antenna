import * as L from 'leaflet'
import { RefObject, useEffect } from 'react'
import { MapContainer, TileLayer, useMapEvents } from 'react-leaflet'
import {
  ATTRIBUTION,
  DEFAULT_ZOOM,
  MAX_BOUNDS,
  MIN_ZOOM,
  setup,
  TILE_LAYER_URL,
} from '../config'
import { MinimapControl } from '../minimap-control'
import styles from '../styles.module.scss'
import { MarkerPosition } from '../types'
import { EditableMarker } from './editable-marker'

setup()

export const EditableMap = ({
  center,
  mapRef,
  markerPosition,
  onLocationLoaded,
  onMarkerPositionChange,
}: {
  center: MarkerPosition
  mapRef: RefObject<L.Map>
  markerPosition: MarkerPosition
  onLocationLoaded?: () => void
  onMarkerPositionChange: (markerPosition: MarkerPosition) => void
}) => {
  // Center map when marker position is updated
  useEffect(() => {
    const map = mapRef?.current
    if (map) {
      map.setView(markerPosition, map.getZoom())
    }
  }, [markerPosition])

  return (
    <MapContainer
      center={center}
      className={styles.mapContainer}
      maxBounds={MAX_BOUNDS}
      minZoom={MIN_ZOOM}
      ref={mapRef}
      scrollWheelZoom
      zoom={DEFAULT_ZOOM}
    >
      <MapContent
        markerPosition={markerPosition}
        onLocationLoaded={onLocationLoaded}
        onMarkerPositionChange={onMarkerPositionChange}
      />
    </MapContainer>
  )
}

const MapContent = ({
  markerPosition,
  onMarkerPositionChange,
  onLocationLoaded,
}: {
  markerPosition: MarkerPosition
  onMarkerPositionChange: (markerPosition: MarkerPosition) => void
  onLocationLoaded?: () => void
}) => {
  useMapEvents({
    click(e) {
      onMarkerPositionChange(e.latlng)
    },
    locationfound(e) {
      onMarkerPositionChange(e.latlng)
      onLocationLoaded?.()
    },
    locationerror() {
      // TODO: Show error alert
      onLocationLoaded?.()
    },
  })

  return (
    <>
      <TileLayer attribution={ATTRIBUTION} url={TILE_LAYER_URL} />
      <EditableMarker
        position={markerPosition}
        onPositionChange={(updatedMarkerPosition) =>
          onMarkerPositionChange(updatedMarkerPosition)
        }
      />
      <MinimapControl />
    </>
  )
}
