import { Deployment } from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Input, InputValue } from 'design-system/components/input/input'
import { STRING, translate } from 'utils/language'
import styles from './deployment-details.module.scss'

export const DeploymentDetailsForm = ({
  deployment,
  onCancelClick,
}: {
  deployment?: Deployment
  onCancelClick: () => void
}) => {
  if (!deployment) {
    return null
  }

  return (
    <>
      <Dialog.Header title={translate(STRING.DETAILS_LABEL_EDIT_DEPLOYMENT)}>
        <div className={styles.buttonWrapper}>
          <Button label={translate(STRING.CANCEL)} onClick={onCancelClick} />
          <Button label={translate(STRING.SAVE)} theme={ButtonTheme.Success} />
        </div>
      </Dialog.Header>
      <div className={styles.content}></div>
    </>
  )
}
