import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useResetPasswordConfirm } from 'data-services/hooks/auth/useResetPasswordConfirm'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { usePageBreadcrumb } from 'utils/usePageBreadcrumb'
import styles from './auth.module.scss'

const SEARCH_PARAM_KEY = 'token'

interface ResetPasswordConfirmValues {
  uid: string
  new_password: string
}

const config: FormConfig = {
  uid: {
    label: translate(STRING.FIELD_LABEL_EMAIL),
    rules: {
      required: true,
    },
  },
  new_password: {
    label: translate(STRING.FIELD_LABEL_NEW_PASSWORD),
    description: translate(STRING.MESSAGE_PASSWORD_FORMAT),
    rules: {
      required: true,
      minLength: 8,
    },
  },
}

export const ResetPasswordConfirm = () => {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState<string>()
  const { resetPasswordConfirm, isLoading, isSuccess, error } =
    useResetPasswordConfirm(() => {
      setEmail(getValues('uid'))
      reset()
    })
  const {
    control,
    handleSubmit,
    getValues,

    reset,
    setError: setFieldError,
  } = useForm<ResetPasswordConfirmValues>({
    defaultValues: {
      uid: '',
      new_password: '',
    },
  })
  const errorMessage = useFormError({ error, setFieldError })

  usePageBreadcrumb({
    title: 'Set password',
    path: APP_ROUTES.RESET_PASSWORD_CONFIRM,
  })

  return (
    <>
      <div className={styles.intro}>
        <h1 className={styles.title}>Set password</h1>
        <p className={styles.text}>
          Please set a new password for your acccount.
        </p>
      </div>
      <form
        className={styles.form}
        onSubmit={handleSubmit((values) =>
          resetPasswordConfirm({
            ...values,
            token: searchParams.get(SEARCH_PARAM_KEY) ?? undefined,
          })
        )}
      >
        {!isSuccess && (
          <>
            <FormField name="uid" config={config} control={control} />
            <FormField
              name="new_password"
              type="password"
              config={config}
              control={control}
            />
            <Button
              label={
                isLoading ? translate(STRING.SAVED) : translate(STRING.SAVE)
              }
              type="submit"
              theme={ButtonTheme.Success}
              loading={isLoading}
            />
          </>
        )}
        {isSuccess && (
          <p className={classNames(styles.text, styles.success)}>
            Password has been updated for <strong>{email}</strong>!
          </p>
        )}
        {errorMessage && (
          <p className={classNames(styles.text, styles.error)}>
            {errorMessage}
          </p>
        )}
      </form>
      <div className={styles.outro}>
        <p className={styles.text}>
          <Link to={APP_ROUTES.LOGIN}>Back to login</Link>
        </p>
      </div>
    </>
  )
}
