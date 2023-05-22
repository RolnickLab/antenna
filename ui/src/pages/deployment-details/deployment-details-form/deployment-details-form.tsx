import { FormField } from 'components/form-field'
import { Deployment } from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Input, InputValue } from 'design-system/components/input/input'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useState } from 'react'
import { Control, useForm, UseFormSetValue } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import styles from '../deployment-details.module.scss'

interface DeploymentDetailsFormProps {
  deployment: Deployment
  onCancelClick: () => void
}

interface DeploymentDetailsFieldValues {
  name: string
  device: string
  latitude?: number
  longitude?: number
  site: string
}

export const DeploymentDetailsForm = ({
  deployment,
  onCancelClick,
}: DeploymentDetailsFormProps) => {
  const { control, handleSubmit, setValue } =
    useForm<DeploymentDetailsFieldValues>({
      defaultValues: {
        name: deployment.name,
        device: '',
        latitude: deployment.location.lat,
        longitude: deployment.location.lng,
        site: '',
      },
    })

  return (
    <form
      onSubmit={handleSubmit((data: any) => {
        console.log('data: ', data)
      })}
    >
      <Dialog.Header title={translate(STRING.DETAILS_LABEL_EDIT_DEPLOYMENT)}>
        <div className={styles.buttonWrapper}>
          <Button label={translate(STRING.CANCEL)} onClick={onCancelClick} />
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
      </div>
    </form>
  )
}

const BaseSection = ({
  control,
  deployment,
}: {
  control: Control<DeploymentDetailsFieldValues>
  deployment: Deployment
}) => {
  return (
    <div className={styles.section}>
      <div className={styles.sectionContent}>
        <div className={styles.sectionRow}>
          <InputValue
            label={translate(STRING.DETAILS_LABEL_DEPLOYMENT_ID)}
            value={deployment.id}
          />
          <FormField
            name="name"
            control={control}
            rules={{ required: true }}
            render={({ field, fieldState }) => (
              <Input
                {...field}
                label={`${translate(STRING.DETAILS_LABEL_NAME)} *`}
                error={fieldState.error?.message}
              />
            )}
          />
        </div>
        <div className={styles.sectionRow}>
          <FormField
            name="device"
            control={control}
            render={({ field, fieldState }) => (
              <Input
                {...field}
                label={translate(STRING.DETAILS_LABEL_DEVICE)}
                error={fieldState.error?.message}
              />
            )}
          />
          <FormField
            name="site"
            control={control}
            render={({ field, fieldState }) => (
              <Input
                {...field}
                label={translate(STRING.DETAILS_LABEL_SITE)}
                error={fieldState.error?.message}
              />
            )}
          />
        </div>
      </div>
    </div>
  )
}

const LocationSection = ({
  control,
  deployment,
  setValue,
}: {
  control: Control<DeploymentDetailsFieldValues>
  deployment: Deployment
  setValue: UseFormSetValue<DeploymentDetailsFieldValues>
}) => {
  const [markerPosition, setMarkerPosition] = useState(
    new MarkerPosition(deployment.location.lat, deployment.location.lng)
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
            rules={{ min: -90, max: 90 }}
            render={({ field, fieldState }) => (
              <Input
                {...field}
                type="number"
                label={translate(STRING.DETAILS_LABEL_LATITUDE)}
                error={fieldState.error?.message}
                onBlur={(e) => {
                  const lat = _.toNumber(e.currentTarget.value)
                  setMarkerPosition(new MarkerPosition(lat, markerPosition.lng))
                  setValue('latitude', lat)
                  field.onBlur()
                }}
              />
            )}
          />
          <FormField
            name="longitude"
            control={control}
            rules={{ min: -180, max: 180 }}
            render={({ field, fieldState }) => (
              <Input
                {...field}
                type="number"
                label={translate(STRING.DETAILS_LABEL_LONGITUDE)}
                error={fieldState.error?.message}
                onBlur={(e) => {
                  const lng = _.toNumber(e.currentTarget.value)
                  setMarkerPosition(new MarkerPosition(markerPosition.lat, lng))
                  setValue('longitude', lng)
                  field.onBlur()
                }}
              />
            )}
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
