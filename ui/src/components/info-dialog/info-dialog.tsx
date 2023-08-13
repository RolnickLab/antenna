import { usePageDetails } from 'data-services/hooks/pages/usePageDetails'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { STRING, translate } from 'utils/language'
import styles from './info-dialog.module.scss'
import { useActivePage } from './useActivePage'

export const InfoDialog = ({ name, slug }: { name: string; slug: string }) => {
  const { activePage, setActivePage } = useActivePage()
  const { page, isLoading } = usePageDetails(slug)

  return (
    <Dialog.Root
      open={activePage === slug}
      onOpenChange={(open) => setActivePage(open ? slug : undefined)}
    >
      <Dialog.Trigger>
        <Button label={name} theme={ButtonTheme.Plain} />
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        <Dialog.Header title={name} />
        {page ? (
          <div
            dangerouslySetInnerHTML={{ __html: page.html }}
            className={styles.content}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
