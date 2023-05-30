import { Button } from 'design-system/components/button/button'
import { EditableMap } from 'design-system/map/editable-map/editable-map'
import { Map, MarkerPosition } from 'design-system/map/types'
import { useRef, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { GeoSearch } from '../geo-search/geo-search'
import styles from './location-map.module.scss'

export const LocationMap = ({
  center,
  markerPosition,
  resetTo,
  onMarkerPositionChange,
}: {
  center: MarkerPosition
  markerPosition: MarkerPosition
  resetTo?: MarkerPosition
  onMarkerPositionChange: (markerPosition: MarkerPosition) => void
}) => {
  const mapRef = useRef<Map>(null)
  const [loadingLocation, setLoadingLocation] = useState(false)

  const resetDisabled = (() => {
    if (!resetTo) {
      return false
    }
    if (!resetTo.equals(markerPosition)) {
      return false
    }
    return true
  })()

  return (
    <div className={styles.wrapper}>
      <div className={styles.mapControls}>
        <GeoSearch onPositionChange={onMarkerPositionChange} />
        <div className={styles.buttonContainer}>
          <Button
            label={translate(STRING.CURRENT_LOCATION)}
            loading={loadingLocation}
            onClick={() => {
              if (mapRef.current) {
                mapRef.current.locate()
                setLoadingLocation(true)
              }
            }}
          />
          {resetTo && (
            <Button
              disabled={resetDisabled}
              label={translate(STRING.RESET)}
              onClick={() => onMarkerPositionChange(resetTo)}
            />
          )}
        </div>
      </div>
      <EditableMap
        center={center}
        mapRef={mapRef}
        markerPosition={markerPosition}
        onLocationLoaded={() => setLoadingLocation(false)}
        onMarkerPositionChange={onMarkerPositionChange}
      />
    </div>
  )
}
