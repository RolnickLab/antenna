import { FormField } from 'components/form-field'
import { Deployment } from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Input, InputValue } from 'design-system/components/input/input'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import styles from './deployment-details.module.scss'

export const DeploymentDetailsForm = ({
  deployment,
  onCancelClick,
}: {
  deployment: Deployment
  onCancelClick: () => void
}) => {
  const { control, handleSubmit } = useForm({
    defaultValues: {
      name: deployment.name,
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
                    value={field.value}
                    label={translate(STRING.DETAILS_LABEL_NAME)}
                    error={fieldState.error?.message}
                  />
                )}
              />
            </div>
          </div>
        </div>
      </div>
    </form>
  )
}
