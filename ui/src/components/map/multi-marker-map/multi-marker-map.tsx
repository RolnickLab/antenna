import classNames from 'classnames'
import * as L from 'leaflet'
import { LoadingSpinner } from 'nova-ui-kit'
import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import {
  ATTRIBUTION,
  DEFAULT_ZOOM,
  MAX_BOUNDS,
  MIN_ZOOM,
  TILE_LAYER_URL,
  setup,
} from '../config'
import { MinimapControl } from '../minimap-control'
import styles from '../styles.module.scss'
import { MarkerPosition } from '../types'

setup()

// Hovering opens a marker's popup. Leaflet toggles the popup on click, and a tap also
// reports a hover, so a click reopens it after the toggle to leave it open either way.
const POPUP_EVENT_HANDLERS: L.LeafletEventHandlerFnMap = {
  mouseover: (e) => e.target.openPopup(),
  click: (e) => setTimeout(() => e.target.openPopup()),
}

export const MultiMarkerMap = ({
  className,
  markers,
  isLoading,
  maxZoom,
}: {
  className?: string
  markers: { position: MarkerPosition; popupContent?: JSX.Element }[]
  isLoading?: boolean
  maxZoom?: number
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
      mapRef.current?.fitBounds(bounds, { maxZoom })
    })
  }, [mapRef, bounds, maxZoom])

  if (isLoading) {
    return (
      <div className={classNames(styles.mapContainer, className)}>
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <MapContainer
      // Fitting the bounds on creation gives the map a view before the minimap
      // reads it, also when there are no markers. The zoom cap stops a single
      // marker resolving to an infinite zoom before the tile layer sets a maximum.
      bounds={bounds}
      boundsOptions={{ maxZoom: DEFAULT_ZOOM }}
      className={classNames(styles.mapContainer, className)}
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
          eventHandlers={marker.popupContent ? POPUP_EVENT_HANDLERS : undefined}
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
