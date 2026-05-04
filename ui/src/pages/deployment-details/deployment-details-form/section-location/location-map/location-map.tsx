import { EditableMap } from 'design-system/map/editable-map/editable-map'
import { Map, MarkerPosition } from 'design-system/map/types'
import { Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useRef, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { GeoSearch } from '../geo-search/geo-search'
import styles from './location-map.module.scss'

export const LocationMap = ({
  center,
  markerPosition,

  onMarkerPositionChange,
}: {
  center: MarkerPosition
  markerPosition: MarkerPosition

  onMarkerPositionChange: (markerPosition: MarkerPosition) => void
}) => {
  const mapRef = useRef<Map>(null)
  const [loadingLocation, setLoadingLocation] = useState(false)

  return (
    <div className={styles.wrapper}>
      <div className={styles.mapControls}>
        <GeoSearch onPositionChange={onMarkerPositionChange} />
        <div className={styles.buttonContainer}>
          <Button
            disabled={loadingLocation}
            onClick={() => {
              if (mapRef.current) {
                mapRef.current.locate()
                setLoadingLocation(true)
              }
            }}
            size="small"
            variant="outline"
          >
            <span>{translate(STRING.CURRENT_LOCATION)}</span>
            {loadingLocation ? (
              <Loader2Icon className="w-4 h-4 animate-spin" />
            ) : null}
          </Button>
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
