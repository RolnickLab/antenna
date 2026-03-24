import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { DeploymentFieldValues } from 'data-services/models/deployment-details'
import { MarkerPosition } from 'design-system/map/types'
import _ from 'lodash'
import { Button } from 'nova-ui-kit'
import { useContext, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { config } from '../config'
import { Section } from '../types'
import { LocationMap } from './location-map/location-map'

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
  const { formSectionRef, formState, setFormSectionValues } =
    useContext(FormContext)

  const defaultValues = useMemo(
    () => ({
      ...DEFAULT_VALUES,
      ..._.omitBy(formState[Section.Location].values, isEmpty),
    }),
    [formState]
  )

  const defaultMarkerPosition = new MarkerPosition(
    defaultValues.latitude,
    defaultValues.longitude
  )

  const { control, handleSubmit, setValue } =
    useForm<SectionLocationFieldValues>({
      defaultValues,
      mode: 'onBlur',
    })

  useSyncSectionStatus(Section.Location, control)

  const [markerPosition, setMarkerPosition] = useState(defaultMarkerPosition)

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.Location, values)
      )}
    >
      <FormSection title={translate(STRING.FIELD_LABEL_LOCATION)}>
        <LocationMap
          center={markerPosition}
          markerPosition={markerPosition}
          onMarkerPositionChange={(updatedMarkesPosition) => {
            const updatedLat = _.round(updatedMarkesPosition.lat, 5)
            const updatedLng = _.round(updatedMarkesPosition.lng, 5)
            setValue('latitude', updatedLat, {
              shouldDirty: true,
              shouldTouch: true,
            })
            setValue('longitude', updatedLng, {
              shouldDirty: true,
              shouldTouch: true,
            })
            setMarkerPosition(new MarkerPosition(updatedLat, updatedLng))
          }}
        />
        <FormRow>
          <FormField
            name="latitude"
            control={control}
            config={config}
            type="number"
            step={1 / 100000}
            noArrows
            onBlur={(e) => {
              const lat = _.toNumber(e.currentTarget.value)
              setValue('latitude', lat)
              setMarkerPosition(new MarkerPosition(lat, markerPosition.lng))
            }}
          />
          <FormField
            name="longitude"
            control={control}
            config={config}
            type="number"
            step={1 / 100000}
            noArrows
            onBlur={(e) => {
              const lng = _.toNumber(e.currentTarget.value)
              setValue('longitude', lng)
              setMarkerPosition(new MarkerPosition(markerPosition.lat, lng))
            }}
          />
        </FormRow>
      </FormSection>
      <FormActions>
        <Button onClick={onBack} size="small" variant="outline">
          <span>{translate(STRING.BACK)}</span>
        </Button>
        <Button onClick={onNext} size="small" variant="success">
          <span>{translate(STRING.NEXT)}</span>
        </Button>
      </FormActions>
    </form>
  )
}
