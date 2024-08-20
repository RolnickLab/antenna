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
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { useForm } from 'react-hook-form'
import { API_MAX_UPLOAD_SIZE } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { bytesToMB } from 'utils/numberFormats'
import { useFormError } from 'utils/useFormError'
import { UserInfo } from 'utils/user/types'
import { UserInfoImageUpload } from '../user-info-image-upload/user-info-image-upload'

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
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<UserInfoFormValues>({
    defaultValues: {
      name: userInfo.name,
    },
    mode: 'onChange',
  })
  const { updateUserInfo, error, isLoading, isSuccess } = useUpdateUserInfo()
  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form onSubmit={handleSubmit((values) => updateUserInfo(values))}>
      {errorMessage && (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      )}
      <FormSection>
        <FormRow>
          <InputValue
            label={translate(STRING.FIELD_LABEL_EMAIL)}
            value={userInfo.email}
          />
          <InputValue
            label={translate(STRING.FIELD_LABEL_PASSWORD)}
            value={translate(STRING.MESSAGE_CHANGE_PASSWORD)}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="name"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
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
        </FormRow>
      </FormSection>
      <FormActions>
        <Button
          label={isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}
          icon={isSuccess ? IconType.RadixCheck : undefined}
          type="submit"
          theme={ButtonTheme.Success}
          loading={isLoading}
        />
      </FormActions>
    </form>
  )
}
