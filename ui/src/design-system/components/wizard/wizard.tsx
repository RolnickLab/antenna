import * as Accordion from '@radix-ui/react-accordion'
import { ReactNode, forwardRef } from 'react'
import styles from './wizard.module.scss'

const Root = ({
  children,
  defaultValue,
  value,
  onValueChange,
}: {
  children: ReactNode
  defaultValue?: string
  value?: string
  onValueChange?: (value?: string) => void
}) => (
  <Accordion.Root
    className={styles.accordionRoot}
    type="single"
    defaultValue={defaultValue}
    collapsible
    value={value}
    onValueChange={onValueChange}
  >
    {children}
  </Accordion.Root>
)

const Item = ({ value, children }: { value: string; children: ReactNode }) => (
  <Accordion.Item className={styles.accordionItem} value={value}>
    {children}
  </Accordion.Item>
)

const Trigger = forwardRef<
  HTMLButtonElement,
  { title: string; children?: ReactNode }
>(({ title, children }, forwardedRef) => (
  <Accordion.Header className={styles.accordionHeader}>
    <Accordion.Trigger ref={forwardedRef} className={styles.accordionTrigger}>
      <div className={styles.extra}>{children}</div>
      {title}
    </Accordion.Trigger>
  </Accordion.Header>
))

const Content = forwardRef<HTMLDivElement, { children: ReactNode }>(
  ({ children, ...props }, forwardedRef) => (
    <Accordion.Content
      ref={forwardedRef}
      {...props}
      className={styles.accordionContent}
    >
      <div className={styles.content}>{children}</div>
    </Accordion.Content>
  )
)

export { Content, Item, Root, Trigger }
