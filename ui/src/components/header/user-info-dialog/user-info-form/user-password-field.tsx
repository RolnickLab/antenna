import { FormField } from 'components/form/form-field'
import { FormError } from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { useUpdateUserPassword } from 'data-services/hooks/auth/useUpdateUserPassword'
import { SaveButton } from 'design-system/components/button/save-button'
import {
  EditableInput,
  InputContent,
  InputValue,
} from 'design-system/components/input/input'
import { Button } from 'nova-ui-kit'
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
    label: translate(STRING.FIELD_LABEL_PASSWORD_NEW),
    description: translate(STRING.MESSAGE_PASSWORD_FORMAT),
    rules: {
      required: true,
      minLength: 8,
    },
  },
  current_password: {
    label: translate(STRING.FIELD_LABEL_PASSWORD_CURRENT),
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
          name="current_password"
          type="password"
          config={config}
          control={control}
        />
        <FormField
          name="new_password"
          type="password"
          config={config}
          control={control}
        />
        <div className={styles.miniFormActions}>
          <Button size="small" variant="ghost" onClick={() => onCancel()}>
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
        </div>
      </div>
    </form>
  )
}
