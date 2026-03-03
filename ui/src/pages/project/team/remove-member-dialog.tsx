import { FormError, FormSection } from 'components/form/layout/layout'
import { useRemoveMember } from 'data-services/hooks/team/useRemoveMember'
import { Member } from 'data-services/models/member'
import * as Dialog from 'design-system/components/dialog/dialog'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CheckIcon, Loader2Icon, XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

export const RemoveMemberDialog = ({ member }: { member: Member }) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { removeMember, isLoading, isSuccess, error } = useRemoveMember(
    projectId as string
  )
  const errorMessage = useFormError({ error })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <BasicTooltip asChild content={translate(STRING.REMOVE_MEMBER)}>
        <Dialog.Trigger asChild>
          <Button
            aria-label={translate(STRING.REMOVE_MEMBER)}
            size="icon"
            variant="ghost"
          >
            <XIcon className="w-4 h-4" />
          </Button>
        </Dialog.Trigger>
      </BasicTooltip>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        {errorMessage && (
          <FormError
            intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
            message={errorMessage}
          />
        )}
        <FormSection
          title={translate(STRING.REMOVE_MEMBER)}
          description={translate(STRING.MESSAGE_REMOVE_MEMBER_CONFIRM, {
            user: member.email,
          })}
        >
          <div className="flex justify-end gap-4">
            <Button
              onClick={() => setIsOpen(false)}
              size="small"
              variant="outline"
            >
              <span>{translate(STRING.CANCEL)}</span>
            </Button>
            <Button
              disabled={isSuccess}
              onClick={() => removeMember(member.id)}
              size="small"
              variant="destructive"
            >
              <span>
                {isSuccess
                  ? translate(STRING.CONFIRMED)
                  : translate(STRING.CONFIRM)}
              </span>
              {isSuccess ? (
                <CheckIcon className="w-4 h-4" />
              ) : isLoading ? (
                <Loader2Icon className="w-4 h-4 animate-spin" />
              ) : null}
            </Button>
          </div>
        </FormSection>
      </Dialog.Content>
    </Dialog.Root>
  )
}
