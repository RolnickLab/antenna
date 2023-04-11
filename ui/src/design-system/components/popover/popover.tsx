import * as Popover from '@radix-ui/react-popover'
import { ReactNode } from 'react'
import { Icon, IconType } from '../icon/icon'
import styles from './popover.module.scss'

const Root = ({ children }: { children: ReactNode }) => (
  <Popover.Root>{children}</Popover.Root>
)

const Trigger = ({ children }: { children: ReactNode }) => (
  <Popover.Trigger asChild>{children}</Popover.Trigger>
)

const Content = ({
  ariaCloselabel,
  align,
  side,
  children,
}: {
  ariaCloselabel: string
  align?: 'start' | 'center' | 'end'
  side?: 'top' | 'right' | 'bottom' | 'left'
  children: ReactNode
}) => (
  <Popover.Portal>
    <Popover.Content
      className={styles.popoverContent}
      align={align}
      side={side}
      sideOffset={6}
    >
      {children}
      <Popover.Close
        className={styles.popoverClose}
        aria-label={ariaCloselabel}
      >
        <Icon type={IconType.Close} size={12} />
      </Popover.Close>
      <Popover.Arrow className={styles.popoverArrow} />
    </Popover.Content>
  </Popover.Portal>
)

export { Root, Trigger, Content }
