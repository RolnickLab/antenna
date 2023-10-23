import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useLogin } from 'data-services/hooks/auth/useLogin'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { useFormError } from 'utils/useFormError'
import { usePageBreadcrumb } from 'utils/usePageBreadcrumb'
import styles from './auth.module.scss'

interface LoginFormValues {
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
    rules: {
      required: true,
    },
  },
}

export const Login = () => {
  const { state } = useLocation()
  const navigate = useNavigate()
  const { login, isLoading, error } = useLogin({
    onSuccess: () => navigate(state?.to ?? APP_ROUTES.HOME),
  })
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<LoginFormValues>({
    defaultValues: { email: state?.email ?? '', password: '' },
  })
  const errorMessage = useFormError({ error, setFieldError })

  usePageBreadcrumb({
    title: 'Login',
    path: APP_ROUTES.LOGIN,
  })

  return (
    <>
      <h1 className={styles.title}>Login</h1>
      <form
        className={styles.form}
        onSubmit={handleSubmit((values) => login(values))}
      >
        <FormField name="email" type="text" config={config} control={control} />
        <FormField
          name="password"
          type="password"
          config={config}
          control={control}
        />
        <Button
          label="Login"
          type="submit"
          theme={ButtonTheme.Success}
          loading={isLoading}
        />
        {errorMessage && (
          <p className={classNames(styles.text, styles.error)}>
            {errorMessage}
          </p>
        )}
        <p className={styles.text}>
          No account yet? <Link to={APP_ROUTES.SIGN_UP}>Sign up</Link>
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
