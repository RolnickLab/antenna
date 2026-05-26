import * as Tabs from '@radix-ui/react-tabs'
import { ReactNode } from 'react'
import styles from './tabs.module.scss'

const Root = ({
  children,
  defaultValue,
  value,
  onValueChange,
}: {
  children: ReactNode
  defaultValue?: string

  value?: string
  onValueChange?: (value: string) => void
}) => (
  <Tabs.Root
    className={styles.tabsRoot}
    defaultValue={defaultValue}
    value={value}
    onValueChange={onValueChange}
  >
    {children}
  </Tabs.Root>
)

const List = ({
  ariaLabel,
  children,
}: {
  ariaLabel?: string
  children: ReactNode
}) => (
  <Tabs.List aria-label={ariaLabel} className={styles.tabsList}>
    {children}
  </Tabs.List>
)

const Trigger = ({ value, label }: { value: string; label: string }) => (
  <Tabs.Trigger value={value} className={styles.tabsTrigger}>
    <span className={styles.label}>{label}</span>
  </Tabs.Trigger>
)

const Content = ({
  value,
  children,
}: {
  value: string
  children: ReactNode
}) => (
  <Tabs.Content value={value} tabIndex={-1}>
    {children}
  </Tabs.Content>
)

export { Content, List, Root, Trigger }
