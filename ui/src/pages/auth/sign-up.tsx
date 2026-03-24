import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useSignUp } from 'data-services/hooks/auth/useSignUp'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button, buttonVariants } from 'nova-ui-kit'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
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
        <Button type="submit" variant="success" loading={isLoading}>
          <span>{translate(STRING.SIGN_UP)}</span>
          {isLoading ? <Loader2Icon className="w-4 h-4 animate-spin" /> : null}
        </Button>
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
              <CheckIcon className="w-4 h-4" />
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
        <Link
          className={buttonVariants({ size: 'small', variant: 'outline' })}
          to={APP_ROUTES.HOME}
        >
          <span>{translate(STRING.VIEW_PUBLIC_PROJECTS)}</span>
        </Link>
      </div>
    </>
  )
}
