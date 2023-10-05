import * as Dialog from '@radix-ui/react-dialog'
import classNames from 'classnames'
import { ReactNode } from 'react'
import { Icon, IconType } from '../icon/icon'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
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
  isCompact,
  isLoading,
  onOpenAutoFocus,
}: {
  ariaCloselabel: string
  children: ReactNode
  isCompact?: boolean
  isLoading?: boolean
  onOpenAutoFocus?: (event: Event) => void
}) => (
  <Dialog.Portal>
    <Dialog.Overlay className={styles.dialogOverlay}>
      {isLoading ? (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      ) : null}
    </Dialog.Overlay>
    <Dialog.Content
      className={classNames(styles.dialog, {
        [styles.compact]: isCompact,
        [styles.loading]: isLoading,
      })}
      onOpenAutoFocus={onOpenAutoFocus}
    >
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

export { Content, Header, Root, Trigger }
