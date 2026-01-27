import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { SUCCESS_TIMEOUT } from 'data-services/constants'
import { useAddMember } from 'data-services/hooks/team/useAddMember'
import { SaveButton } from 'design-system/components/button/save-button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputContent } from 'design-system/components/input/input'
import { PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { RolesPicker } from './roles-picker'

const config: FormConfig = {
  email: {
    label: translate(STRING.FIELD_LABEL_EMAIL),
    rules: {
      required: true,
    },
  },
  role_id: {
    label: translate(STRING.FIELD_LABEL_ROLE),
    rules: {
      required: true,
    },
  },
}

interface AddMemberFormValues {
  email: string
  role_id: string
}

export const AddMemberDialog = () => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const {
    addMember,
    error,
    isLoading,
    isSuccess,
    reset: resetHook,
  } = useAddMember(projectId as string)
  const {
    control,
    handleSubmit,
    reset: resetForm,
    setError: setFieldError,
  } = useForm<AddMemberFormValues>({
    defaultValues: { email: '', role_id: 'BasicMember' },
  })
  const errorMessage = useFormError({ error, setFieldError })

  // Reset on open state change
  useEffect(() => {
    resetHook()
    resetForm()
  }, [isOpen])

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>
            {translate(STRING.ENTITY_ADD, {
              type: translate(STRING.ENTITY_TYPE_MEMBER),
            })}
          </span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        {errorMessage && (
          <FormError
            intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
            message={errorMessage}
          />
        )}
        <form
          onSubmit={handleSubmit(async (values) => {
            await addMember({ email: values.email, roleId: values.role_id })
            setTimeout(() => setIsOpen(false), SUCCESS_TIMEOUT)
          })}
        >
          <FormSection
            title={translate(STRING.ENTITY_ADD, {
              type: translate(STRING.ENTITY_TYPE_MEMBER),
            })}
            description="Only users with existing Antenna accounts can be added as members."
          >
            <FormField
              name="email"
              type="text"
              config={config}
              control={control}
            />
            <FormController
              name="role_id"
              control={control}
              config={config.role_id}
              render={({ field, fieldState }) => (
                <InputContent
                  label={config[field.name].label}
                  error={fieldState.error?.message}
                >
                  <RolesPicker
                    value={field.value}
                    onValueChange={field.onChange}
                  />
                </InputContent>
              )}
            />
          </FormSection>
          <FormActions>
            <Button
              onClick={() => setIsOpen(false)}
              size="small"
              variant="outline"
            >
              <span>{translate(STRING.CANCEL)}</span>
            </Button>
            <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
          </FormActions>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  )
}
