import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useLogin } from 'data-services/hooks/auth/useLogin'
import { ExternalLinkIcon, Loader2Icon } from 'lucide-react'
import { Button, buttonVariants } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { APP_ROUTES, LANDING_PAGE_CONTACT_URL } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { usePageBreadcrumb } from 'utils/usePageBreadcrumb'
import styles from './auth.module.scss'

interface LoginFormValues {
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
      <div className={styles.intro}>
        <h1 className={styles.title}>{translate(STRING.LOGIN)}</h1>
      </div>
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
        <Button variant="success" type="submit">
          <span>{translate(STRING.LOGIN)}</span>
          {isLoading ? (
            <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
          ) : null}
        </Button>
        {errorMessage && (
          <p className={classNames(styles.text, styles.error)}>
            {errorMessage}
          </p>
        )}
      </form>
      <div className={styles.outro}>
        <Link
          className={buttonVariants({ size: 'small', variant: 'outline' })}
          to={APP_ROUTES.HOME}
        >
          <span>{translate(STRING.VIEW_PUBLIC_PROJECTS)}</span>
        </Link>
        <a
          href={LANDING_PAGE_CONTACT_URL}
          rel="noreferrer"
          target="_blank"
          className={buttonVariants({ size: 'small', variant: 'outline' })}
        >
          <span>Get in touch</span>
          <ExternalLinkIcon className="w-4 h-4" />
        </a>
      </div>
      <p className={styles.text}>
        {translate(STRING.FORGOT_PASSWORD)} Please reach out and we will help
        you.
      </p>
    </>
  )
}
