import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { STRING, translate } from 'utils/language'
import styles from './info-dialog.module.scss'

export const InfoDialog = ({
  name,
  content,
}: {
  name: string
  content: string
}) => (
  <Dialog.Root>
    <Dialog.Trigger>
      <Button label={name} theme={ButtonTheme.Plain} />
    </Dialog.Trigger>
    <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
      <Dialog.Header title={name} />
      <div
        dangerouslySetInnerHTML={{ __html: content }}
        className={styles.content}
      />
    </Dialog.Content>
  </Dialog.Root>
)
