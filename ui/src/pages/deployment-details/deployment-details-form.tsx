import { FormField } from 'components/form/form-field'
import {
  Deployment,
  DeploymentFieldValues,
} from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useState } from 'react'
import { Control, useForm, UseFormSetValue } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { config } from './config'
import styles from './styles.module.scss'

const DEFAULT_VALUES: DeploymentFieldValues = {
  device: '',
  name: '',
  latitude: 0,
  longitude: 0,
  path: '',
  site: '',
}

export const DeploymentDetailsForm = ({
  deployment,
  title,
  onCancelClick,
  onSubmit,
}: {
  deployment: Deployment
  title: string
  onCancelClick: () => void
  onSubmit: (data: DeploymentFieldValues) => void
}) => {
  const { control, handleSubmit, setValue } = useForm<DeploymentFieldValues>({
    defaultValues: {
      ...DEFAULT_VALUES,
      ..._.omitBy(
        {
          name: deployment.name,
          latitude: deployment.latitude,
          longitude: deployment.longitude,
          path: deployment.path,
        },
        _.isUndefined
      ),
    },
    mode: 'onBlur',
  })

  return (
    <form
      onSubmit={handleSubmit((data: DeploymentFieldValues) => onSubmit(data))}
    >
      <Dialog.Header title={title}>
        <div className={styles.buttonWrapper}>
          <Button
            label={translate(STRING.CANCEL)}
            onClick={onCancelClick}
            type="button"
          />
          <Button
            label={translate(STRING.SAVE)}
            theme={ButtonTheme.Success}
            type="submit"
          />
        </div>
      </Dialog.Header>
      <div className={styles.content}>
        <BaseSection control={control} deployment={deployment} />
        <LocationSection
          control={control}
          deployment={deployment}
          setValue={setValue}
        />
        <SourceImageSection control={control} />
      </div>
    </form>
  )
}

const BaseSection = ({
  control,
  deployment,
}: {
  control: Control<DeploymentFieldValues>
  deployment: Deployment
}) => (
  <div className={styles.section}>
    <div className={styles.sectionContent}>
      <div className={styles.sectionRow}>
        <InputValue
          label={translate(STRING.DETAILS_LABEL_DEPLOYMENT_ID)}
          value={deployment.id}
        />
        <FormField name="name" control={control} config={config} />
      </div>
      <div className={styles.sectionRow}>
        <FormField name="device" control={control} config={config} />
        <FormField name="site" control={control} config={config} />
      </div>
    </div>
  </div>
)

const LocationSection = ({
  control,
  deployment,
  setValue,
}: {
  control: Control<DeploymentFieldValues>
  deployment: Deployment
  setValue: UseFormSetValue<DeploymentFieldValues>
}) => {
  const [markerPosition, setMarkerPosition] = useState(
    new MarkerPosition(deployment.latitude, deployment.longitude)
  )

  return (
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
    </div>
  )
}

const SourceImageSection = ({
  control,
}: {
  control: Control<DeploymentFieldValues>
}) => (
  <div className={styles.section}>
    <h2 className={styles.sectionTitle}>
      {translate(STRING.DETAILS_LABEL_SOURCE_IMAGES)}
    </h2>
    <div className={styles.sectionContent}>
      <div className={styles.sectionRow}>
        <FormField name="path" control={control} config={config} />
      </div>
    </div>
  </div>
)
