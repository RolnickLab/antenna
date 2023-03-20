import * as Tabs from '@radix-ui/react-tabs'
import { ReactNode } from 'react'
import { Icon, IconType } from '../icon/icon'
import styles from './tabs.module.scss'

const Root = ({
  defaultValue,
  children,
}: {
  defaultValue?: string
  children: ReactNode
}) => (
  <Tabs.Root defaultValue={defaultValue} className={styles.tabsRoot}>
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

const Trigger = ({
  value,
  label,
  icon,
}: {
  value: string
  label: string
  icon?: IconType
}) => (
  <Tabs.Trigger value={value} className={styles.tabsTrigger}>
    {icon && <Icon type={icon} />}
    <span>{label}</span>
  </Tabs.Trigger>
)

const Content = ({
  value,
  children,
}: {
  value: string
  children: ReactNode
}) => (
  <Tabs.Content value={value} className={styles.tabsContent}>
    {children}
  </Tabs.Content>
)

export { Root, List, Trigger, Content }
