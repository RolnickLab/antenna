import styles from './info-block.module.scss'

interface Field {
  label: string
  value: string
}

export const InfoBlock = ({ fields }: { fields: Field[] }) => (
  <>
    {fields.map((field, index) => (
      <p className={styles.field} key={index}>
        <span className={styles.fieldLabel}>{field.label}</span>
        <span className={styles.fieldValue}>{field.value}</span>
      </p>
    ))}
  </>
)
