import * as Popover from '@radix-ui/react-popover'
import classNames from 'classnames'
import { ReactNode } from 'react'
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
  className,
  container,
  disableOutsideClose,
  hideClose,
  side,
}: {
  align?: 'start' | 'center' | 'end'
  ariaCloselabel: string
  children: ReactNode
  className?: string
  container?: HTMLElement
  disableOutsideClose?: boolean
  hideClose?: boolean
  side?: 'top' | 'right' | 'bottom' | 'left'
}) => (
  <Popover.Portal container={container}>
    <Popover.Content
      className={classNames(styles.popoverContent, className)}
      align={align}
      side={side}
      sideOffset={6}
      collisionPadding={{ bottom: 64 }}
      onInteractOutside={(e) => {
        if (disableOutsideClose) {
          e.preventDefault()
        }
      }}
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
