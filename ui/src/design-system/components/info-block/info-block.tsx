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
  label,
}: {
  children: ReactNode
  label: string
}) => (
  <div className="w-full grid gap-1">
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
        <Link to={to}>
          <span
            className={classNames('body-base', 'text-primary font-semibold', {
              [styles.bubble]: _.isNumber(_value),
            })}
          >
            {valueLabel}
          </span>
        </Link>
      ) : (
        <span className="body-base">{valueLabel}</span>
      )}
    </>
  )
}
