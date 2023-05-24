import { FormField } from 'components/form/form-field'
import { DeploymentFieldValues } from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useContext, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { isEmpty } from 'utils/isEmpty'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { config } from './config'
import { Section } from './deployment-details-form'
import { FormContext } from './formContext'

type SectionLocationFieldValues = Pick<
  DeploymentFieldValues,
  'latitude' | 'longitude'
>

const DEFAULT_VALUES: SectionLocationFieldValues = {
  latitude: 0,
  longitude: 0,
}

export const SectionLocation = ({
  onBack,
  onNext,
}: {
  onBack: () => void
  onNext: () => void
}) => {
  const {
    formSectionRef,
    formState,
    setFormSectionStatus,
    setFormSectionValues,
  } = useContext(FormContext)

  const defaultValues = {
    ...DEFAULT_VALUES,
    ..._.omitBy(formState[Section.Location].values, isEmpty),
  }

  const {
    control,
    handleSubmit,
    formState: { isDirty, isValid },
    setValue,
  } = useForm<SectionLocationFieldValues>({
    defaultValues,
    mode: 'onBlur',
  })

  const [markerPosition, setMarkerPosition] = useState(
    new MarkerPosition(defaultValues.latitude, defaultValues.longitude)
  )

  useEffect(() => {
    setFormSectionStatus(Section.Location, { isDirty, isValid })
  }, [isDirty, isValid])

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.Location, values)
      )}
    >
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
            onClick={onNext}
            theme={ButtonTheme.Success}
          />
        </div>
      </div>
    </form>
  )
}
