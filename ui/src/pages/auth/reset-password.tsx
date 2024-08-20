import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useResetPassword } from 'data-services/hooks/auth/useResetPassword'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { usePageBreadcrumb } from 'utils/usePageBreadcrumb'
import styles from './auth.module.scss'

interface ResetFormValues {
  email: string
}

const config: FormConfig = {
  email: {
    label: translate(STRING.FIELD_LABEL_EMAIL),
    rules: {
      required: true,
    },
  },
}

export const ResetPassword = () => {
  const [email, setEmail] = useState<string>()
  const { state } = useLocation()
  const { resetPassword, isLoading, isSuccess, error } = useResetPassword(() =>
    setEmail(getValues('email'))
  )
  const {
    control,
    handleSubmit,
    getValues,
    setError: setFieldError,
  } = useForm<ResetFormValues>({
    defaultValues: { email: state?.email ?? '' },
  })

  const errorMessage = useFormError({ error, setFieldError })

  usePageBreadcrumb({
    title: 'Forgot password?',
    path: APP_ROUTES.RESET_PASSWORD,
  })

  return (
    <>
      <div className={styles.intro}>
        <h1 className={styles.title}>Forgot password?</h1>
        {!isSuccess && (
          <p className={styles.text}>
            No worries, we'll send you reset instructions.
          </p>
        )}
      </div>
      <form
        className={styles.form}
        onSubmit={handleSubmit((values) => resetPassword(values))}
      >
        {!isSuccess && (
          <>
            <FormField
              name="email"
              type="text"
              config={config}
              control={control}
            />
            <Button
              label="Send instructions"
              type="submit"
              theme={ButtonTheme.Success}
              loading={isLoading}
            />
          </>
        )}
        {isSuccess && (
          <p className={classNames(styles.text, styles.success)}>
            Reset intructions has been sent to <strong>{email}</strong>!
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
          <Link to={APP_ROUTES.LOGIN} state={{ email }}>
            Back to login
          </Link>
        </p>
      </div>
    </>
  )
}
