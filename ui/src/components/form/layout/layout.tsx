import classNames from 'classnames'
import { CSSProperties, ReactNode } from 'react'
import styles from './layout.module.scss'

export const FormError = ({
  inDialog,
  intro,
  message,
  style,
}: {
  inDialog?: boolean
  intro?: string
  message: string
  style?: CSSProperties
}) => (
  <div
    className={classNames(styles.formError, { [styles.inDialog]: inDialog })}
    style={style}
  >
    {intro ? `${intro}: ${message}` : message}
  </div>
)

export const FormSection = ({
  children,
  style,
  title,
  description,
}: {
  children?: ReactNode
  style?: CSSProperties
  title?: string
  description?: string
}) => (
  <div className={styles.section} style={style}>
    {title && (
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>{title}</h2>
        {description && (
          <h2 className={styles.sectionDescription}>{description}</h2>
        )}
      </div>
    )}
    <div className={styles.sectionContent}>{children}</div>
  </div>
)

export const FormRow = ({
  children,
  style,
}: {
  children: ReactNode
  style?: CSSProperties
}) => (
  <div className={styles.sectionRow} style={style}>
    {children}
  </div>
)

export const FormActions = ({
  children,
  style,
}: {
  children: ReactNode
  style?: CSSProperties
}) => (
  <div className={classNames(styles.section, styles.formActions)} style={style}>
    {children}
  </div>
)
