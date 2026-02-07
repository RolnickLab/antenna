import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { SUCCESS_TIMEOUT } from 'data-services/constants'
import { useUpdateMember } from 'data-services/hooks/team/useUpdateMember'
import { Member } from 'data-services/models/member'
import { SaveButton } from 'design-system/components/button/save-button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputContent } from 'design-system/components/input/input'
import { Button } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { RolesPicker } from './roles-picker'

export const ManageAccessDialog = ({ member }: { member: Member }) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const [roleId, setRoleId] = useState<string>(member.role.id)
  const { updateMember, isLoading, isSuccess, error } = useUpdateMember(
    projectId as string,
    member.id
  )
  const errorMessage = useFormError({ error })

  // Reset form on open state change
  useEffect(() => setRoleId(member.role.id), [isOpen, member])

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <span>{translate(STRING.MANAGE_ACCESS)}</span>
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
          title={translate(STRING.MANAGE_ACCESS)}
          description={translate(STRING.MANAGE_ACCESS_FOR, {
            user: member.email,
          })}
        >
          <InputContent label={translate(STRING.FIELD_LABEL_ROLE)}>
            <RolesPicker value={roleId} onValueChange={setRoleId} />
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
              await updateMember({ roleId })
              setTimeout(() => setIsOpen(false), SUCCESS_TIMEOUT)
            }}
          />
        </FormActions>
      </Dialog.Content>
    </Dialog.Root>
  )
}
