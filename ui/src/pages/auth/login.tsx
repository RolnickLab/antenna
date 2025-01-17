import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useLogin } from 'data-services/hooks/auth/useLogin'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import buttonStyles from 'design-system/components/button/button.module.scss'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { APP_ROUTES, LANDING_PAGE_WAITLIST_URL } from 'utils/constants'
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
    getValues,
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
        <Button
          label={translate(STRING.LOGIN)}
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
          {translate(STRING.FORGOT_PASSWORD)}{' '}
          <Link
            to={APP_ROUTES.RESET_PASSWORD}
            state={{ email: getValues('email') ?? undefined }}
          >
            {translate(STRING.RESET)}
          </Link>
        </p>
        {/* TODO: Add link to join waitlist */}
        <p className={classNames(styles.text, styles.divider)}>
          {translate(STRING.OR).toUpperCase()}
        </p>
        <Link className={buttonStyles.button} to={APP_ROUTES.HOME}>
          <span className={buttonStyles.label}>
            {translate(STRING.VIEW_PUBLIC_PROJECTS)}
          </span>
        </Link>
        <a
          href={LANDING_PAGE_WAITLIST_URL}
          rel="noreferrer"
          target="_blank"
          className={buttonStyles.button}
        >
          <span className={buttonStyles.label}>
            {translate(STRING.SIGN_UP)}
          </span>
          <Icon
            type={IconType.ExternalLink}
            theme={IconTheme.Primary}
            size={14}
          />
        </a>
      </div>
    </>
  )
}
