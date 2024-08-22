import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useSignUp } from 'data-services/hooks/auth/useSignUp'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { usePageBreadcrumb } from 'utils/usePageBreadcrumb'
import styles from './auth.module.scss'

interface SignUpFormValues {
  email: string
  password: string
}

const config: FormConfig = {
  email: {
    label: translate(STRING.FIELD_LABEL_EMAIL),
    rules: {
      required: true,
    },
  },
  password: {
    label: translate(STRING.FIELD_LABEL_PASSWORD),
    description: translate(STRING.MESSAGE_PASSWORD_FORMAT),
    rules: {
      required: true,
      minLength: 8,
    },
  },
}

export const SignUp = () => {
  const navigate = useNavigate()
  const [signedUpEmail, setSignedUpEmail] = useState<string | undefined>()
  const {
    control,
    getValues,
    handleSubmit,
    resetField,
    setError: setFieldError,
  } = useForm<SignUpFormValues>({
    defaultValues: { email: '', password: '' },
  })
  const { signUp, isLoading, isSuccess, error } = useSignUp({
    onSuccess: () => {
      setSignedUpEmail(getValues('email'))
      resetField('email')
      resetField('password')
    },
  })
  const errorMessage = useFormError({ error, setFieldError })

  usePageBreadcrumb({
    title: 'Sign up',
    path: APP_ROUTES.SIGN_UP,
  })

  return (
    <>
      <h1 className={styles.title}>{translate(STRING.SIGN_UP)}</h1>
      <form
        className={styles.form}
        onSubmit={handleSubmit((values) =>
          signUp({ email: values.email, password: values.password })
        )}
      >
        <FormField name="email" type="text" config={config} control={control} />
        <FormField
          name="password"
          type="password"
          config={config}
          control={control}
        />
        <Button
          label={translate(STRING.SIGN_UP)}
          type="submit"
          theme={ButtonTheme.Success}
          loading={isLoading}
        />
        {errorMessage && (
          <p className={classNames(styles.text, styles.error)}>
            {errorMessage}
          </p>
        )}
      </form>
      <div className={styles.outro}>
        <p className={styles.text}>
          {isSuccess ? (
            <>
              <Icon
                type={IconType.Checkmark}
                size={12}
                theme={IconTheme.Success}
              />
              <span>{translate(STRING.MESSAGE_SIGNED_UP)}</span>
            </>
          ) : (
            <span>{translate(STRING.MESSAGE_HAS_ACCOUNT)}</span>
          )}{' '}
          <Link
            to={APP_ROUTES.LOGIN}
            state={isSuccess ? { email: signedUpEmail } : undefined}
          >
            {translate(STRING.LOGIN)}
          </Link>
        </p>
        <p className={classNames(styles.text, styles.divider)}>
          {translate(STRING.OR).toUpperCase()}
        </p>
        <Button
          label={translate(STRING.VIEW_PUBLIC_PROJECTS)}
          type="button"
          theme={ButtonTheme.Default}
          onClick={() => navigate(APP_ROUTES.HOME)}
        />
      </div>
    </>
  )
}
