import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useSignUp } from 'data-services/hooks/auth/useSignUp'
import { parseServerError } from 'data-services/utils'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import styles from './auth.module.scss'

interface SignUpFormValues {
  email: string
  password: string
}

const config: FormConfig = {
  email: {
    label: 'Email',
    rules: {
      required: true,
    },
  },
  password: {
    label: 'Password',
    description:
      'The password must contain at least 8 characters and cannot be entirely numeric.',
    rules: {
      required: true,
      minLength: 8,
    },
  },
}

export const SignUp = () => {
  const [serverError, setServerError] = useState<string | undefined>()
  const [signedUpEmail, setSignedUpEmail] = useState<string | undefined>()

  const navigate = useNavigate()
  const { control, getValues, handleSubmit, resetField, setError } =
    useForm<SignUpFormValues>({
      defaultValues: { email: '', password: '' },
    })
  const { signUp, isLoading, isSuccess, error } = useSignUp({
    onSuccess: () => {
      setSignedUpEmail(getValues('email'))
      resetField('email')
      resetField('password')
    },
  })

  useEffect(() => {
    if (error) {
      const { message, fieldErrors } = parseServerError(error)
      setServerError(fieldErrors.length ? undefined : message)
      fieldErrors.forEach((error) => {
        setError(
          error.key as any,
          { message: error.message },
          { shouldFocus: true }
        )
      })
    } else {
      setServerError(undefined)
    }
  }, [error])

  return (
    <>
      <h1 className={styles.title}>Sign up</h1>
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
          label="Sign up"
          type="submit"
          theme={ButtonTheme.Success}
          loading={isLoading}
        />
        {serverError ? (
          <p className={classNames(styles.text, styles.error)}>{serverError}</p>
        ) : null}
        <p className={styles.text}>
          {isSuccess ? (
            <>
              <Icon
                type={IconType.Checkmark}
                size={12}
                theme={IconTheme.Success}
              />
              <span>Signed up successfully!</span>
            </>
          ) : (
            <span>Already have an account?</span>
          )}
          <Link
            to={APP_ROUTES.LOGIN}
            state={isSuccess ? { email: signedUpEmail } : undefined}
          >
            Login
          </Link>
        </p>
        <p className={classNames(styles.text, styles.divider)}>OR</p>
        <Button
          label="View public projects"
          type="button"
          theme={ButtonTheme.Default}
          onClick={() => navigate(APP_ROUTES.HOME)}
        />
      </form>
    </>
  )
}
