import classNames from 'classnames'
import _ from 'lodash'
import {
  ChangeEvent,
  CSSProperties,
  FocusEvent,
  forwardRef,
  ReactNode,
  useState,
} from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import { BasicTooltip } from '../tooltip/basic-tooltip'
import styles from './input.module.scss'

interface InputProps {
  description?: string
  disabled?: boolean
  error?: string
  label: string
  name: string
  noArrows?: boolean
  placeholder?: string
  step?: number
  type?: 'text' | 'number' | 'password'
  value?: string | number
  onBlur?: (e: FocusEvent<HTMLInputElement>) => void
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void
  onFocus?: (e: FocusEvent<HTMLInputElement>) => void
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ ...props }, forwardedRef) => {
    const {
      description,
      disabled,
      error,
      label,
      name,
      noArrows,
      step = 'any',
      type: initialType,
      ...rest
    } = props
    const [type, setType] = useState(initialType)

    const hasDescription = !!description?.length
    const descriptionId = hasDescription ? `description-${name}` : undefined

    const hasError = !!error?.length
    const errorId = error ? `error-${name}` : undefined

    return (
      <div className={styles.container}>
        <div className={styles.labelRow}>
          <label className={styles.label} htmlFor={name}>
            {label}
          </label>
          {hasError ? (
            <span id={errorId} className={styles.error}>
              {error}
            </span>
          ) : undefined}
        </div>
        <div className={styles.inputContainer}>
          <input
            aria-disabled={disabled}
            aria-describedby={descriptionId}
            aria-errormessage={errorId}
            aria-invalid={hasError}
            autoComplete="off"
            className={classNames(styles.input, {
              [styles.password]: initialType === 'password',
              [styles.noArrows]: noArrows,
            })}
            disabled={disabled}
            id={name}
            name={name}
            ref={forwardedRef}
            step={type === 'number' ? step : undefined}
            type={type}
            {...rest}
          />
          {initialType === 'password' && !disabled ? (
            <div className={styles.passwordButtonContainer}>
              <BasicTooltip
                align="end"
                asChild
                content={`${type === 'password' ? 'Show' : 'Hide'} password`}
              >
                <IconButton
                  icon={IconType.BatchId}
                  theme={IconButtonTheme.Plain}
                  onClick={() =>
                    setType(type === 'password' ? 'text' : 'password')
                  }
                />
              </BasicTooltip>
            </div>
          ) : null}
        </div>
        {hasDescription ? (
          <span id={descriptionId} className={styles.description}>
            {description}
          </span>
        ) : undefined}
      </div>
    )
  }
)

export const InputValue = ({
  label,
  value,
  to,
}: {
  label: string
  value?: string | number
  to?: string
}) => {
  const valueLabel =
    value === undefined || value === ''
      ? translate(STRING.VALUE_NOT_AVAILABLE)
      : _.isNumber(value)
      ? value.toLocaleString()
      : value

  return (
    <InputContent label={label}>
      {to ? (
        <Link to={to} className={classNames(styles.value, styles.link)}>
          {value}
        </Link>
      ) : (
        <span className="body-small text-muted-foreground">{valueLabel}</span>
      )}
    </InputContent>
  )
}

export const InputContent = ({
  description,
  error,
  label,
  style,
  children,
}: {
  description?: string
  error?: string
  label: string
  style?: CSSProperties
  children?: ReactNode
}) => {
  const hasError = !!error?.length
  const hasDescription = !!description?.length

  return (
    <div className={styles.container} style={style}>
      <div className={styles.labelRow}>
        <span className={styles.label}>{label}</span>
        {hasError ? <span className={styles.error}>{error}</span> : undefined}
      </div>
      <div className={styles.content}>{children}</div>
      {hasDescription ? (
        <span className={styles.description}>{description}</span>
      ) : undefined}
    </div>
  )
}

export const LockedInput = ({
  editing,
  setEditing,
  onCancel,
  onSubmit,
  children,
}: {
  editing: boolean
  setEditing: (editing: boolean) => void
  onCancel: () => void
  onSubmit: () => void
  children: ReactNode
}) => (
  <div className={styles.lockedInputContainer}>
    <div className={styles.editButtonContainer}>
      <IconButton
        icon={editing ? IconType.Cross : IconType.Pencil}
        onClick={() => {
          if (editing) {
            setEditing(false)
            onCancel()
          } else {
            setEditing(true)
          }
        }}
      />
      {editing && (
        <IconButton
          icon={IconType.RadixCheck}
          onClick={() => {
            setEditing(false)
            onSubmit()
          }}
        />
      )}
    </div>

    {children}
  </div>
)

export const EditableInput = ({
  editing,
  onEdit,
  children,
}: {
  editing: boolean
  onEdit: () => void
  children: ReactNode
}) => (
  <div className={styles.lockedInputContainer}>
    <div className={styles.editButtonContainer}>
      {!editing && (
        <IconButton icon={IconType.Pencil} onClick={() => onEdit()} />
      )}
    </div>
    {children}
  </div>
)
