import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
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
  const { control, handleSubmit } = useForm<LoginFormValues>()

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
          onSubmit={handleSubmit((values) => {
            console.log('values: ', values)
          })}
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
          <Button label="Login" type="submit" theme={ButtonTheme.Success} />
          <p className={styles.text}>
            No account? <Link to="#">Sign up</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
