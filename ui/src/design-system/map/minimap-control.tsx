import { useEventHandlers, useLeafletContext } from '@react-leaflet/core'
import * as L from 'leaflet'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  MapContainer,
  Rectangle,
  TileLayer,
  useMap,
  useMapEvent,
} from 'react-leaflet'
import { MAX_BOUNDS, setup, TILE_LAYER_URL } from './config'

setup()

const MINIMAP_BOUNDS_OPTIONS = { weight: 1 }
const MINIMAP_STYLE = { height: 80, width: 80 }
const MINIMAP_ZOOM = 1

const MinimapBounds = ({
  parentMap,
  zoom,
}: {
  parentMap: L.Map
  zoom: number
}) => {
  const minimap = useMap()
  const context = useLeafletContext()
  const [bounds, setBounds] = useState(parentMap.getBounds())

  // Update parent map center on minimap click
  const onClick = useCallback(
    (e: L.LeafletMouseEvent) => {
      parentMap.setView(e.latlng, parentMap.getZoom())
    },
    [parentMap]
  )
  useMapEvent('click', onClick)

  // Update minimap view on parent map change
  const handlers = useMemo(() => {
    const onChange = () => {
      setBounds(parentMap.getBounds())
      minimap.setView(parentMap.getCenter(), zoom)
    }
    return { move: onChange, zoom: onChange }
  }, [minimap, parentMap, zoom])
  useEventHandlers({ instance: parentMap, context }, handlers)

  return (
    <Rectangle
      bounds={bounds}
      interactive={false}
      pathOptions={MINIMAP_BOUNDS_OPTIONS}
    />
  )
}

export const MinimapControl = () => {
  const parentMap = useMap()
  const [renderMinimap, setRenderMinimap] = useState(false)

  useEffect(() => {
    requestAnimationFrame(() => {
      setRenderMinimap(!!parentMap)
    })
  }, [parentMap])

  if (!renderMinimap) {
    return null
  }

  return (
    <div className="leaflet-bottom leaflet-left">
      <div className="leaflet-control leaflet-bar">
        <MapContainer
          attributionControl={false}
          center={parentMap.getCenter()}
          doubleClickZoom={false}
          dragging={false}
          maxBounds={MAX_BOUNDS}
          scrollWheelZoom={false}
          style={MINIMAP_STYLE}
          zoom={MINIMAP_ZOOM}
          zoomControl={false}
        >
          <TileLayer url={TILE_LAYER_URL} />
          <MinimapBounds parentMap={parentMap} zoom={MINIMAP_ZOOM} />
        </MapContainer>
      </div>
    </div>
  )
}
