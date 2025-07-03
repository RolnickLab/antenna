import classNames from 'classnames'
import _ from 'lodash'
import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import styles from './info-block.module.scss'

interface Field {
  label: string
  value?: string | number
  to?: string
}

export const InfoBlock = ({ fields }: { fields: Field[] }) => (
  <div className="grid gap-6">
    {fields.map((field, index) => (
      <InfoBlockField key={index} label={field.label}>
        <InfoBlockFieldValue value={field.value} to={field.to} />
      </InfoBlockField>
    ))}
  </div>
)

export const InfoBlockField = ({
  children,
  className,
  label,
}: {
  children: ReactNode
  className?: string
  label: string
}) => (
  <div className={classNames('w-full grid gap-1', className)}>
    <span className="body-overline font-semibold text-muted-foreground">
      {label}
    </span>
    {children}
  </div>
)

export const InfoBlockFieldValue = ({
  value,
  to,
}: {
  value?: string | number
  to?: string
}) => {
  const _value =
    value === undefined ? translate(STRING.VALUE_NOT_AVAILABLE) : value
  const valueLabel = _.isNumber(_value) ? _value.toLocaleString() : _value

  return (
    <>
      {to ? (
        <Link className="body-base" to={to}>
          <span
            className={
              _.isNumber(_value) ? styles.bubble : 'text-primary font-semibold'
            }
          >
            {valueLabel}
          </span>
        </Link>
      ) : (
        <span>{valueLabel}</span>
      )}
    </>
  )
}
