import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useLogin } from 'data-services/hooks/auth/useLogin'
import { serverErrorToString } from 'data-services/utils'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import styles from './login.module.scss'

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
  const navigate = useNavigate()
  const { login, isLoading, error } = useLogin({
    onSuccess: () => navigate('/'),
  })
  const { control, handleSubmit } = useForm<LoginFormValues>({
    defaultValues: { email: '', password: '' },
  })

  return (
    <div className={styles.wrapper}>
      <div className={styles.imageWrapper}>
        <video autoPlay muted loop>
          <source
            src="https://leps.fieldguide.ai/public/img/videos/caterpillar.mp4"
            type="video/mp4"
          ></source>
        </video>
      </div>
      <div className={styles.content}>
        <h1 className={styles.title}>Welcome to AMI Platform!</h1>
        <form
          className={styles.form}
          onSubmit={handleSubmit((values) => login(values))}
        >
          <FormField
            name="email"
            type="text"
            config={config}
            control={control}
          />
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
          {error ? (
            <p className={classNames(styles.text, styles.error)}>
              {serverErrorToString(error)}
            </p>
          ) : null}
          <p className={styles.text}>
            No account? <Link to="#">Sign up</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
