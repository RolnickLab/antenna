import { FormField } from 'components/form/form-field'
import { FormError } from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { useUpdateUserEmail } from 'data-services/hooks/auth/useUpdateUserEmail'
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

interface UpdateEmailFormValues {
  current_password: string
  new_email: string
}

const config: FormConfig = {
  new_email: {
    label: translate(STRING.FIELD_LABEL_EMAIL_NEW),
    rules: {
      required: true,
    },
  },
  current_password: {
    label: translate(STRING.FIELD_LABEL_PASSWORD_CURRENT),
    rules: {
      required: true,
    },
  },
}

export const UserEmailField = ({ value }: { value?: string }) => {
  const [editing, setEditing] = useState(false)

  return (
    <EditableInput editing={editing} onEdit={() => setEditing(true)}>
      {editing ? (
        <InputContent label={translate(STRING.FIELD_LABEL_EMAIL)}>
          <UpdateEmailForm onCancel={() => setEditing(false)} />
        </InputContent>
      ) : (
        <InputValue label={translate(STRING.FIELD_LABEL_EMAIL)} value={value} />
      )}
    </EditableInput>
  )
}

const UpdateEmailForm = ({ onCancel }: { onCancel: () => void }) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<UpdateEmailFormValues>({
    defaultValues: {
      current_password: '',
      new_email: '',
    },
    mode: 'onChange',
  })
  const { updateUserEmail, error, isLoading, isSuccess } = useUpdateUserEmail(
    () => setTimeout(() => onCancel(), CLOSE_TIMEOUT)
  )
  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      className={styles.miniForm}
      onSubmit={handleSubmit((values) => updateUserEmail(values))}
    >
      {errorMessage && (
        <FormError
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
          style={{ padding: '8px 16px' }}
        />
      )}
      <div className={styles.miniFormContent}>
        <FormField name="new_email" config={config} control={control} />
        <FormField
          name="current_password"
          type="password"
          config={config}
          control={control}
        />
        <div className={styles.miniFormActions}>
          <Button onClick={() => onCancel()} size="small" variant="ghost">
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
        </div>
      </div>
    </form>
  )
}
