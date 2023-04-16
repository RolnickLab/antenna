import classNames from 'classnames'
import { Link } from 'react-router-dom'
import styles from './info-block.module.scss'

interface Field {
  label: string
  value: string
  to?: string
}

export const InfoBlock = ({ fields }: { fields: Field[] }) => (
  <>
    {fields.map((field, index) => (
      <p className={styles.field} key={index}>
        <span className={styles.fieldLabel}>{field.label}</span>
        {field.to ? (
          <Link to={field.to}>
            <span className={classNames(styles.fieldValue, styles.link)}>
              {field.value}
            </span>
          </Link>
        ) : (
          <span className={styles.fieldValue}>{field.value}</span>
        )}
      </p>
    ))}
  </>
)
