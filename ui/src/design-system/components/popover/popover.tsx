import * as Popover from '@radix-ui/react-popover'
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
  onMouseEnter,
  onMouseLeave,
}: {
  asChild?: boolean
  children: ReactNode
  onMouseEnter?: () => void
  onMouseLeave?: () => void
}) => (
  <Popover.Trigger
    asChild={asChild}
    onMouseEnter={onMouseEnter}
    onMouseLeave={onMouseLeave}
  >
    {children}
  </Popover.Trigger>
)

const Content = ({
  ariaCloselabel,
  align,
  side,
  children,
  hideClose,
}: {
  ariaCloselabel: string
  align?: 'start' | 'center' | 'end'
  side?: 'top' | 'right' | 'bottom' | 'left'
  children: ReactNode
  hideClose?: boolean
}) => (
  <Popover.Portal>
    <Popover.Content
      className={styles.popoverContent}
      align={align}
      side={side}
      sideOffset={6}
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

export { Root, Trigger, Content }
