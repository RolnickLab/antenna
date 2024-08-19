import { FormField } from 'components/form/form-field'
import { FormError } from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { useUpdateUserPassword } from 'data-services/hooks/auth/useUpdateUserPassword'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import {
  EditableInput,
  InputContent,
  InputValue,
} from 'design-system/components/input/input'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import styles from './user-info-form.module.scss'

const CLOSE_TIMEOUT = 1000

interface UpdatePasswordFormValues {
  current_password: string
  new_password: string
}

const config: FormConfig = {
  new_password: {
    label: 'New password',
    rules: {
      required: true,
    },
  },
  current_password: {
    label: 'Current password',
    rules: {
      required: true,
    },
  },
}

export const UserPasswordField = ({ value }: { value: string }) => {
  const [editing, setEditing] = useState(false)

  return (
    <EditableInput editing={editing} onEdit={() => setEditing(true)}>
      {editing ? (
        <InputContent label={translate(STRING.FIELD_LABEL_PASSWORD)}>
          <UpdatePasswordForm onCancel={() => setEditing(false)} />
        </InputContent>
      ) : (
        <InputValue
          label={translate(STRING.FIELD_LABEL_PASSWORD)}
          value={value}
        />
      )}
    </EditableInput>
  )
}

const UpdatePasswordForm = ({ onCancel }: { onCancel: () => void }) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<UpdatePasswordFormValues>({
    defaultValues: {
      current_password: '',
      new_password: '',
    },
    mode: 'onChange',
  })
  const { updateUserPassword, error, isLoading, isSuccess } =
    useUpdateUserPassword(() => setTimeout(() => onCancel(), CLOSE_TIMEOUT))
  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      className={styles.miniForm}
      onSubmit={handleSubmit((values) => updateUserPassword(values))}
    >
      {errorMessage && (
        <FormError
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
          style={{ padding: '8px 16px' }}
        />
      )}
      <div className={styles.miniFormContent}>
        <FormField
          name="new_password"
          type="password"
          config={config}
          control={control}
        />
        <FormField
          name="current_password"
          type="password"
          config={config}
          control={control}
        />
        <div className={styles.miniFormActions}>
          <Button
            label={translate(STRING.CANCEL)}
            theme={ButtonTheme.Plain}
            onClick={() => onCancel()}
          />
          <Button
            label={translate(STRING.SAVE)}
            icon={isSuccess ? IconType.RadixCheck : undefined}
            type="submit"
            theme={ButtonTheme.Success}
            loading={isLoading}
            disabled={isLoading || isSuccess}
          />
        </div>
      </div>
    </form>
  )
}
