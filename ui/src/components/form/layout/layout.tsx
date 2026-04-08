import classNames from 'classnames'
import { CircleAlert, InfoIcon, LightbulbIcon } from 'lucide-react'
import { CSSProperties, ReactNode } from 'react'
import styles from './layout.module.scss'

export const FormMessage = ({
  children,
  className,
  message,
  theme = 'success',
  withIcon,
}: {
  className?: string
  message: string
  theme?: 'success' | 'warning' | 'destructive'
  withIcon?: boolean
  children?: ReactNode
}) => {
  const Icon = {
    success: LightbulbIcon,
    warning: InfoIcon,
    destructive: CircleAlert,
  }[theme]

  return (
    <div
      className={classNames(
        'px-4 py-2 rounded-md body-small',
        {
          'bg-[#d8f2ec] text-[#078c6e]': theme === 'success',
          'bg-warning-50 text-warning-700': theme === 'warning',
          'bg-destructive-50 text-destructive-700': theme === 'destructive',
        },
        className
      )}
    >
      {withIcon ? <Icon className="inline w-4 h-4 mr-2" /> : null}
      <span>{message}</span>
      {children}
    </div>
  )
}

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
    className={classNames(
      styles.formError,
      'w-full bg-destructive-50 text-destructive-700 body-small',
      { [styles.inDialog]: inDialog }
    )}
    style={style}
  >
    {intro ? <span className={styles.intro}>{intro}: </span> : null}
    <span>{message}</span>
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
