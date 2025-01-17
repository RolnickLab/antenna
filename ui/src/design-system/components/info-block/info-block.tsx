import classNames from 'classnames'
import _ from 'lodash'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import styles from './info-block.module.scss'

interface Field {
  label: string
  value?: string | number
  to?: string
}

export const InfoBlock = ({ fields }: { fields: Field[] }) => (
  <>
    {fields.map((field, index) => {
      const value =
        field.value === undefined
          ? translate(STRING.VALUE_NOT_AVAILABLE)
          : field.value
      const valueLabel = _.isNumber(value) ? value.toLocaleString() : value

      return (
        <p className={styles.field} key={index}>
          <span className={styles.fieldLabel}>{field.label}</span>
          {field.to ? (
            <Link to={field.to}>
              <span
                className={classNames(styles.fieldValue, styles.link, {
                  [styles.bubble]: _.isNumber(value),
                })}
              >
                {valueLabel}
              </span>
            </Link>
          ) : (
            <span className={styles.fieldValue}>{valueLabel}</span>
          )}
        </p>
      )
    })}
  </>
)
