import classNames from 'classnames'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useUpdateUserInfo } from 'data-services/hooks/auth/useUpdateUserInfo'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { InputValue } from 'design-system/components/input/input'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { UserInfo } from 'utils/user/types'
import styles from './user-info-form.module.scss'

interface UserInfoFormValues {
  name?: string
}

const config: FormConfig = {
  name: {
    label: 'Name',
  },
}

export const UserInfoForm = ({ userInfo }: { userInfo: UserInfo }) => {
  const [serverError, setServerError] = useState<string | undefined>()
  const { control, handleSubmit, setError } = useForm<UserInfoFormValues>({
    defaultValues: {
      name: userInfo.name,
    },
  })
  const { updateUserInfo, isLoading, error } = useUpdateUserInfo()

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
      <form
        className={styles.form}
        onSubmit={handleSubmit((values) =>
          updateUserInfo({
            name: values.name,
          })
        )}
      >
        {serverError ? (
          <div className={styles.formError}>
            <span>Could not save: </span>
            <span>{serverError}</span>
          </div>
        ) : null}
        <div className={styles.section}>
          <div className={styles.sectionContent}>
            <div className={styles.sectionRow}>
              <InputValue label="Email" value="To be added" />
              <InputValue label="Password" value="Reset button to be added" />
            </div>
            <div className={styles.sectionRow}>
              <FormField
                name="name"
                type="text"
                config={config}
                control={control}
              />
            </div>
          </div>
        </div>

        <div className={classNames(styles.section, styles.formActions)}>
          <Button
            label={translate(STRING.SAVE)}
            type="submit"
            theme={ButtonTheme.Success}
            loading={isLoading}
          />
        </div>
      </form>
    </>
  )
}
