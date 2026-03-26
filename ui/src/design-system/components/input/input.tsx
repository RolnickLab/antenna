import classNames from 'classnames'
import _ from 'lodash'
import { CheckIcon, EyeIcon, PenIcon, XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import {
  ChangeEvent,
  CSSProperties,
  FocusEvent,
  forwardRef,
  ReactNode,
  useMemo,
  useState,
} from 'react'
import { Link } from 'react-router-dom'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
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
          <label className="body-small font-semibold" htmlFor={name}>
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
                <Button
                  aria-label={type === 'password' ? 'Show' : 'Hide'}
                  onClick={() =>
                    setType(type === 'password' ? 'text' : 'password')
                  }
                  size="icon"
                  type="button"
                  variant="ghost"
                >
                  <EyeIcon className="w-4 h-4" />
                </Button>
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
  value?: string | number | Date
  to?: string
}) => {
  const valueLabel = useMemo(() => {
    if (value === undefined || value === '') {
      return translate(STRING.VALUE_NOT_AVAILABLE)
    }

    if (_.isNumber(value)) {
      return value.toLocaleString()
    }

    if (_.isDate(value)) {
      return getFormatedDateTimeString({ date: value })
    }

    return value
  }, [value])

  return (
    <InputContent label={label}>
      {to ? (
        <Link to={to} className="body-small text-primary font-semibold">
          {valueLabel}
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
        <span className="body-small font-semibold">{label}</span>
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
      <Button
        aria-label={editing ? translate(STRING.CANCEL) : translate(STRING.EDIT)}
        onClick={() => {
          if (editing) {
            setEditing(false)
            onCancel()
          } else {
            setEditing(true)
          }
        }}
        size="icon"
        type="button"
        variant="ghost"
      >
        {editing ? (
          <XIcon className="w-4 h-4" />
        ) : (
          <PenIcon className="w-4 h-4" />
        )}
      </Button>
      {editing && (
        <Button
          aria-label={translate(STRING.CONFIRM)}
          onClick={() => {
            setEditing(false)
            onSubmit()
          }}
          size="icon"
          type="button"
          variant="ghost"
        >
          <CheckIcon className="w-4 h-4" />
        </Button>
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
        <Button
          aria-label={translate(STRING.EDIT)}
          onClick={() => onEdit()}
          size="icon"
          type="button"
          variant="ghost"
        >
          <PenIcon className="w-4 h-4" />
        </Button>
      )}
    </div>
    {children}
  </div>
)
