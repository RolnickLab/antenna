import * as Dialog from '@radix-ui/react-dialog'
import React from 'react'
import styles from './dialog.module.scss'

const Root = ({ children }: { children: React.ReactNode }) => (
  <Dialog.Root>{children}</Dialog.Root>
)

const Trigger = ({ children }: { children: React.ReactNode }) => (
  <Dialog.Trigger asChild>{children}</Dialog.Trigger>
)

const Content = ({
  title,
  ariaCloselabel,
  children,
}: {
  title: string
  ariaCloselabel: string
  children: React.ReactNode
}) => (
  <Dialog.Portal>
    <Dialog.Overlay className={styles.dialogOverlay} />
    <Dialog.Content className={styles.dialogContent}>
      <Dialog.Title className={styles.dialogTitle}>{title}</Dialog.Title>
      {children}
      <Dialog.Close className={styles.dialogClose} aria-label={ariaCloselabel}>
        <span>x</span>
      </Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
)

export { Root, Trigger, Content }
