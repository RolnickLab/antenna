import { DeploymentDetails } from 'data-services/models/deployment-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { DeploymentDetailsForm } from './deployment-details-form/deployment-details-form'

const newDeployment = new DeploymentDetails({
  id: 'new-deployment',
  num_source_images: 18,
})

export const NewDeploymentDialog = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <Button
          label={translate(STRING.DETAILS_LABEL_NEW_DEPLOYMENT)}
          theme={ButtonTheme.Plain}
        />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <DeploymentDetailsForm
          deployment={newDeployment}
          title={translate(STRING.DETAILS_LABEL_NEW_DEPLOYMENT)}
          onCancelClick={() => setIsOpen(false)}
          onSubmit={(data) => {
            // TODO: Hook up with BE
            console.log('onSubmit: ', data)
            setIsOpen(false)
          }}
        />
      </Dialog.Content>
    </Dialog.Root>
  )
}
