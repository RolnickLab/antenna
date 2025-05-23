import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { useUpdateUserInfo } from 'data-services/hooks/auth/useUpdateUserInfo'
import { SaveButton } from 'design-system/components/button/save-button'
import { InputContent } from 'design-system/components/input/input'
import { useRef } from 'react'
import { useForm } from 'react-hook-form'
import { API_MAX_UPLOAD_SIZE } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { bytesToMB } from 'utils/numberFormats'
import { useFormError } from 'utils/useFormError'
import { UserInfo } from 'utils/user/types'
import { UserInfoImageUpload } from '../user-info-image-upload/user-info-image-upload'
import { UserEmailField } from './user-email-field'
import { UserPasswordField } from './user-password-field'

interface UserInfoFormValues {
  name: string
  image?: File | null
}

const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: {
      required: true,
    },
  },
  image: {
    label: translate(STRING.FIELD_LABEL_ICON),
    description: [
      translate(STRING.MESSAGE_IMAGE_SIZE, {
        value: bytesToMB(API_MAX_UPLOAD_SIZE),
        unit: 'MB',
      }),
      translate(STRING.MESSAGE_IMAGE_FORMAT),
    ].join('\n'),
    rules: {
      validate: (file: File) => {
        if (file) {
          if (file?.size > API_MAX_UPLOAD_SIZE) {
            return translate(STRING.MESSAGE_IMAGE_TOO_BIG)
          }
        }
      },
    },
  },
}

export const UserInfoForm = ({ userInfo }: { userInfo: UserInfo }) => {
  const formRef = useRef<HTMLFormElement>(null)
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<UserInfoFormValues>({
    defaultValues: {
      name: userInfo.name,
    },
  })
  const { updateUserInfo, error, isLoading, isSuccess } = useUpdateUserInfo()
  const errorMessage = useFormError({ error, setFieldError })

  return (
    <>
      <FormSection>
        {errorMessage && (
          <FormError
            inDialog
            intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
            message={errorMessage}
          />
        )}
        <FormRow>
          <UserEmailField value={userInfo.email} />
          <UserPasswordField value="************" />
          <form
            ref={formRef}
            onSubmit={handleSubmit((values) => updateUserInfo(values))}
            className="grid gap-8"
          >
            <FormField
              name="name"
              type="text"
              config={config}
              control={control}
            />
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
          </form>
        </FormRow>
      </FormSection>
      <FormActions>
        <SaveButton
          isLoading={isLoading}
          isSuccess={isSuccess}
          onClick={() => {
            formRef.current?.dispatchEvent(
              new Event('submit', { cancelable: true, bubbles: true })
            )
          }}
        />
      </FormActions>
    </>
  )
}
