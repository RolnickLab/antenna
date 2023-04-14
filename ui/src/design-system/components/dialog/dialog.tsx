import * as Dialog from '@radix-ui/react-dialog'
import { ReactNode } from 'react'
import { Icon, IconType } from '../icon/icon'
import styles from './dialog.module.scss'

const Root = ({
  children,
  open,
  onOpenChange,
}: {
  children: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}) => (
  <Dialog.Root open={open} onOpenChange={onOpenChange}>
    {children}
  </Dialog.Root>
)

const Trigger = ({ children }: { children: ReactNode }) => (
  <Dialog.Trigger asChild>{children}</Dialog.Trigger>
)

const Content = ({
  ariaCloselabel,
  children,
}: {
  ariaCloselabel: string
  children: ReactNode
}) => (
  <Dialog.Portal>
    <Dialog.Overlay className={styles.dialogOverlay} />
    <Dialog.Content className={styles.dialog}>
      <div className={styles.dialogContent}>{children}</div>
      <Dialog.Close className={styles.dialogClose} aria-label={ariaCloselabel}>
        <Icon type={IconType.Close} size={12} />
      </Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
)

const Header = ({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) => (
  <div className={styles.dialogHeader}>
    <Dialog.Title className={styles.dialogTitle}>{title}</Dialog.Title>
    {children}
  </div>
)

export { Root, Trigger, Content, Header }
