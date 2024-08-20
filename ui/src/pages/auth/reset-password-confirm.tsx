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
    useResetPasswordConfirm(() => setEmail(getValues('uid')))
  const {
    control,
    handleSubmit,
    getValues,
    setError: setFieldError,
  } = useForm<ResetPasswordConfirmValues>({
    defaultValues: {
      uid: '',
      new_password: '',
    },
  })
  const errorMessage = useFormError({ error, setFieldError })

  usePageBreadcrumb({
    title: translate(STRING.SET_PASSWORD),
    path: APP_ROUTES.RESET_PASSWORD_CONFIRM,
  })

  return (
    <>
      <div className={styles.intro}>
        <h1 className={styles.title}>{translate(STRING.SET_PASSWORD)}</h1>
        {!isSuccess && (
          <p className={styles.text}>
            {translate(STRING.SET_PASSWORD_DETAILS)}
          </p>
        )}
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
        {email && (
          <p
            className={classNames(styles.text, styles.success)}
            dangerouslySetInnerHTML={{
              __html: translate(STRING.MESSAGE_PASSWORD_UPDATED, {
                email: `<strong>${email}</strong>`,
              }),
            }}
          />
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
            {translate(STRING.BACK_TO_LOGIN)}
          </Link>
        </p>
      </div>
    </>
  )
}
