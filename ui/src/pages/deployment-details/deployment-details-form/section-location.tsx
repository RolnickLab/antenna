import { FormField } from 'components/form/form-field'
import {
  Deployment,
  DeploymentFieldValues,
} from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { config } from './config'

type SectionLocationFieldValues = Pick<
  DeploymentFieldValues,
  'latitude' | 'longitude'
>

const DEFAULT_VALUES: SectionLocationFieldValues = {
  latitude: 0,
  longitude: 0,
}

export const SectionLocation = ({
  deployment,
  onBack,
  onSubmit,
}: {
  deployment: Deployment
  onBack: () => void
  onSubmit: (data: SectionLocationFieldValues) => void
}) => {
  const { control, handleSubmit, setValue } =
    useForm<SectionLocationFieldValues>({
      defaultValues: {
        ...DEFAULT_VALUES,
        ..._.omitBy(
          {
            latitude: deployment.latitude,
            longitude: deployment.longitude,
          },
          _.isUndefined
        ),
      },
      mode: 'onBlur',
    })

  const [markerPosition, setMarkerPosition] = useState(
    new MarkerPosition(deployment.latitude, deployment.longitude)
  )

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          {translate(STRING.DETAILS_LABEL_LOCATION)}
        </h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <FormField
              name="latitude"
              control={control}
              config={config}
              type="number"
              onBlur={(e) => {
                const lat = _.toNumber(e.currentTarget.value)
                setMarkerPosition(new MarkerPosition(lat, markerPosition.lng))
                setValue('latitude', lat)
              }}
            />
            <FormField
              name="longitude"
              control={control}
              config={config}
              type="number"
              onBlur={(e) => {
                const lng = _.toNumber(e.currentTarget.value)
                setMarkerPosition(new MarkerPosition(markerPosition.lat, lng))
                setValue('longitude', lng)
              }}
            />
          </div>
          <Map
            center={markerPosition}
            markerPosition={markerPosition}
            markerDraggable
            onMarkerPositionChange={(updatedMarkesPosition) => {
              const updatedLat = _.round(updatedMarkesPosition.lat, 5)
              const updatedLng = _.round(updatedMarkesPosition.lng, 5)

              setValue('latitude', updatedLat)
              setValue('longitude', updatedLng)
              setMarkerPosition(new MarkerPosition(updatedLat, updatedLng))
            }}
          />
        </div>
        <div className={styles.formActions}>
          <Button label={translate(STRING.BACK)} onClick={onBack} />
          <Button
            label={translate(STRING.NEXT)}
            type="submit"
            theme={ButtonTheme.Success}
          />
        </div>
      </div>
    </form>
  )
}
