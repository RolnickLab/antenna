import * as Accordion from '@radix-ui/react-accordion'
import classNames from 'classnames'
import { ReactNode, forwardRef } from 'react'
import { Icon, IconType } from '../icon/icon'
import styles from './wizard.module.scss'

const Root = ({
  children,
  className,
  defaultValue,
  value,
  onValueChange,
}: {
  children: ReactNode
  className?: string
  defaultValue?: string
  value?: string
  onValueChange?: (value?: string) => void
}) => (
  <Accordion.Root
    className={classNames(styles.accordionRoot, className)}
    type="single"
    defaultValue={defaultValue}
    collapsible
    value={value}
    onValueChange={onValueChange}
  >
    {children}
  </Accordion.Root>
)

const Item = ({
  children,
  className,
  value,
}: {
  children: ReactNode
  className?: string
  value: string
}) => (
  <Accordion.Item
    className={classNames(styles.accordionItem, className)}
    value={value}
  >
    {children}
  </Accordion.Item>
)

const Trigger = forwardRef<
  HTMLButtonElement,
  {
    children?: ReactNode
    className?: string
    showToggle?: boolean
    title: string
  }
>(({ children, className, showToggle, title }, forwardedRef) => (
  <Accordion.Header className={styles.accordionHeader}>
    <Accordion.Trigger
      ref={forwardedRef}
      className={classNames(styles.accordionTrigger, className)}
    >
      <div className={styles.extra}>{children}</div>
      {title}
      {showToggle && (
        <div className={styles.toggle}>
          <Icon type={IconType.ToggleDown} />
        </div>
      )}
    </Accordion.Trigger>
  </Accordion.Header>
))

const Content = forwardRef<
  HTMLDivElement,
  { children: ReactNode; className?: string }
>(({ children, className, ...props }, forwardedRef) => (
  <Accordion.Content
    ref={forwardedRef}
    {...props}
    className={styles.accordionContent}
  >
    <div className={classNames(styles.content, className)}>{children}</div>
  </Accordion.Content>
))

export { Content, Item, Root, Trigger }
