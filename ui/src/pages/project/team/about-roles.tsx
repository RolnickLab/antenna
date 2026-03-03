import { FormSection } from 'components/form/layout/layout'
import { useRoles } from 'data-services/hooks/team/useRoles'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InfoIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const AboutRoles = () => {
  const { roles = [] } = useRoles(true)

  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button size="small" variant="ghost">
          <InfoIcon className="w-4 h-4" />
          <span>{translate(STRING.ABOUT_ROLES)}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        className="max-w-lg h-fit"
      >
        <Dialog.Header title={translate(STRING.ABOUT_ROLES)} />
        <FormSection>
          {roles.map((role) => (
            <div key={role.id}>
              <h3 className="body-base font-medium mb-2">{role.name}</h3>
              <p className="body-base">{role.description}</p>
            </div>
          ))}
        </FormSection>
      </Dialog.Content>
    </Dialog.Root>
  )
}
