import classNames from 'classnames'
import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import { FormConfig } from 'components/form/types'
import { useUpdateUserInfo } from 'data-services/hooks/auth/useUpdateUserInfo'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { UserInfo } from 'utils/user/types'
import { UserInfoImageUpload } from '../user-info-image-upload/user-info-image-upload'
import styles from './user-info-form.module.scss'

const IMAGE_MAX_SIZE = 1024 * 1024 // 1MB

interface UserInfoFormValues {
  name?: string
  image?: File | null
}

const config: FormConfig = {
  name: {
    label: 'Name',
  },
  image: {
    label: 'Image',
    description:
      'The image must smaller than 1MB. Valid formats are PNG, GIF and JPEG.',
    rules: {
      validate: (file: File) => {
        if (file) {
          if (file?.size > IMAGE_MAX_SIZE) {
            return translate(STRING.MESSAGE_IMAGE_TOO_BIG)
          }
        }
      },
    },
  },
}

export const UserInfoForm = ({ userInfo }: { userInfo: UserInfo }) => {
  const [serverError, setServerError] = useState<string | undefined>()
  const { control, handleSubmit, setError } = useForm<UserInfoFormValues>({
    defaultValues: {
      name: userInfo.name,
    },
    mode: 'onChange',
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
        onSubmit={handleSubmit((values) => updateUserInfo(values))}
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
              <InputValue label="Email" value={userInfo.email} />
              <InputValue
                label="Password"
                value="Contact an administrator to change your email or password."
              />
            </div>
            <div className={styles.sectionRow}>
              <FormField
                name="name"
                type="text"
                config={config}
                control={control}
              />
            </div>
            <div className={styles.sectionRow}>
              <FormController
                name="image"
                control={control}
                config={config.image}
                render={({ field, fieldState }) => (
                  <InputContent
                    description={config[field.name].description}
                    label={config[field.name].label}
                    error={fieldState.error?.message}
                  >
                    <UserInfoImageUpload
                      userInfo={userInfo}
                      file={field.value}
                      onChange={field.onChange}
                    />
                  </InputContent>
                )}
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
