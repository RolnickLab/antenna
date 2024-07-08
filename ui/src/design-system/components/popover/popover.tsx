import * as Popover from '@radix-ui/react-popover'
import { CSSProperties, ReactNode } from 'react'
import { Icon, IconType } from '../icon/icon'
import styles from './popover.module.scss'

const Root = ({
  children,
  open,
  onOpenChange,
}: {
  children: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}) => (
  <Popover.Root open={open} onOpenChange={onOpenChange}>
    {children}
  </Popover.Root>
)

const Trigger = ({
  asChild = true,
  children,
}: {
  asChild?: boolean
  children: ReactNode
}) => <Popover.Trigger asChild={asChild}>{children}</Popover.Trigger>

const Content = ({
  align,
  ariaCloselabel,
  children,
  container,
  hideClose,
  side,
  style,
}: {
  align?: 'start' | 'center' | 'end'
  ariaCloselabel: string
  children: ReactNode
  container?: HTMLElement
  hideClose?: boolean
  side?: 'top' | 'right' | 'bottom' | 'left'
  style?: CSSProperties
}) => (
  <Popover.Portal container={container}>
    <Popover.Content
      className={styles.popoverContent}
      align={align}
      side={side}
      sideOffset={6}
      style={style}
      collisionPadding={{ bottom: 64 }}
    >
      {children}
      {!hideClose && (
        <Popover.Close
          className={styles.popoverClose}
          aria-label={ariaCloselabel}
        >
          <Icon type={IconType.Close} size={12} />
        </Popover.Close>
      )}
      <Popover.Arrow className={styles.popoverArrow} />
    </Popover.Content>
  </Popover.Portal>
)

export { Content, Root, Trigger }
