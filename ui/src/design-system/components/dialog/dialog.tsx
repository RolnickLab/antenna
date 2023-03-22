import * as Dialog from '@radix-ui/react-dialog'
import React from 'react'
import { Button, ButtonTheme } from '../button/button'
import styles from './dialog.module.scss'

const Root = ({ children }: { children: React.ReactNode }) => (
  <Dialog.Root>{children}</Dialog.Root>
)

const Trigger = ({ children }: { children: React.ReactNode }) => (
  <Dialog.Trigger asChild>{children}</Dialog.Trigger>
)

const Content = ({
  ariaCloselabel,
  children,
}: {
  ariaCloselabel: string
  children: React.ReactNode
}) => (
  <Dialog.Portal>
    <Dialog.Overlay className={styles.dialogOverlay} />
    <Dialog.Content className={styles.dialog}>
      <div className={styles.dialogContent}>{children}</div>
      <Dialog.Close className={styles.dialogClose} aria-label={ariaCloselabel}>
        <span>x</span>
      </Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
)

const Header = ({
  title,
  children,
}: {
  title: string
  children?: React.ReactNode
}) => (
  <div className={styles.dialogHeader}>
    <Dialog.Title className={styles.dialogTitle}>{title}</Dialog.Title>
    {children}
  </div>
)

export { Root, Trigger, Content, Header }
