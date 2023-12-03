import classNames from 'classnames'
import { Link } from 'react-router-dom'
import { STRING } from 'utils/language'
import styles from './info-block.module.scss'

interface Field {
  label: string
  value?: string | number
  to?: string
}

export const InfoBlock = ({ fields }: { fields: Field[] }) => (
  <>
    {fields.map((field, index) => {
      const value = field.value !== undefined ? field.value : STRING.VALUE_NOT_AVAILABLE

      return (
        <p className={styles.field} key={index}>
          <span className={styles.fieldLabel}>{field.label}</span>
          {field.to ? (
            <Link to={field.to}>
              <span className={classNames(styles.fieldValue, styles.link)}>
                {value}
              </span>
            </Link>
          ) : (
            <span className={styles.fieldValue}>{value}</span>
          )}
        </p>
      )
    })}
  </>
)
