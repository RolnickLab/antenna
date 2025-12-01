import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { SUCCESS_TIMEOUT } from 'data-services/constants'
import { useAddMember } from 'data-services/hooks/team/useAddMember'
import { SaveButton } from 'design-system/components/button/save-button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputContent } from 'design-system/components/input/input'
import { PlusIcon } from 'lucide-react'
import { Button, Input } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { RolesPicker } from './roles-picker'

const DEFAULT_ROLE_ID = 'BasicMember'

export const AddMemberDialog = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [roleId, setRoleId] = useState(DEFAULT_ROLE_ID)
  const { isLoading, isSuccess, error } = useAddMember()
  const errorMessage = useFormError({ error })

  // Reset form on open state change
  useEffect(() => {
    setEmail('')
    setRoleId(DEFAULT_ROLE_ID)
  }, [isOpen])

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
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
        <FormSection
          title={translate(STRING.ENTITY_ADD, {
            type: translate(STRING.ENTITY_TYPE_MEMBER),
          })}
        >
          <InputContent label={translate(STRING.FIELD_LABEL_EMAIL)}>
            <Input
              onChange={(e) => setEmail(e.currentTarget.value)}
              type="email"
              value={email}
            />
          </InputContent>
          <InputContent label={translate(STRING.FIELD_LABEL_ROLE)}>
            <RolesPicker onValueChange={setRoleId} value={roleId} />
          </InputContent>
        </FormSection>
        <FormActions>
          <Button
            onClick={() => setIsOpen(false)}
            size="small"
            variant="outline"
          >
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <SaveButton
            isLoading={isLoading}
            isSuccess={isSuccess}
            onClick={async () => {
              setTimeout(() => setIsOpen(false), SUCCESS_TIMEOUT)
            }}
          />
        </FormActions>
      </Dialog.Content>
    </Dialog.Root>
  )
}
