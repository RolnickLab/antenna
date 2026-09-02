import * as L from 'leaflet'
import { useMemo, useRef } from 'react'
import { Marker } from 'react-leaflet'
import { MarkerPosition } from '../types'

export const EditableMarker = ({
  position,
  onPositionChange,
}: {
  position: MarkerPosition
  onPositionChange: (markerPosition: MarkerPosition) => void
}) => {
  const markerRef = useRef<L.Marker>(null)

  const eventHandlers = useMemo(
    () => ({
      dragend() {
        const marker = markerRef.current
        if (marker) {
          onPositionChange(marker.getLatLng())
        }
      },
    }),
    [markerRef]
  )

  return (
    <Marker
      draggable
      eventHandlers={eventHandlers}
      interactive
      position={position}
      ref={markerRef}
    />
  )
}
