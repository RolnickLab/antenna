import { FormError, FormSection } from 'components/form/layout/layout'
import { useRemoveMember } from 'data-services/hooks/team/useRemoveMember'
import { Member } from 'data-services/models/member'
import * as Dialog from 'design-system/components/dialog/dialog'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CheckIcon, Loader2Icon, LogOutIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

export const LeaveTeamDialog = ({ member }: { member: Member }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { removeMember, isLoading, isSuccess, error } = useRemoveMember(
    projectId as string
  )
  const errorMessage = useFormError({ error })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <BasicTooltip asChild content={translate(STRING.LEAVE_TEAM)}>
        <Dialog.Trigger asChild>
          <Button
            aria-label={translate(STRING.LEAVE_TEAM)}
            size="icon"
            variant="ghost"
          >
            <LogOutIcon className="w-4 h-4" />
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
          title={translate(STRING.LEAVE_TEAM)}
          description={translate(STRING.MESSAGE_LEAVE_TEAM_CONFIRM)}
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
              disabled={isLoading || isSuccess}
              onClick={async () => {
                try {
                  await removeMember(member.id)
                  navigate(
                    getAppRoute({
                      to: APP_ROUTES.PROJECTS,
                    })
                  )
                } catch {
                  // Error is handled by hook
                }
              }}
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
