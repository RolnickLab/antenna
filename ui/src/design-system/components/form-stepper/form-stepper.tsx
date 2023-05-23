import classNames from 'classnames'
import styles from './form-stepper.module.scss'

interface FormStepperProps {
  items: {
    id: string
    label: string
  }[]
  currentItem: string
  setCurrentItem: (item: string) => void
}

export const FormStepper = ({
  items,
  currentItem,
  setCurrentItem,
}: FormStepperProps) => {
  return (
    <div className={styles.wrapper}>
      <div className={classNames(styles.item, styles.placeholder)}>
        <span />
        <div className={styles.itemContent}>
          <div className={styles.line} />
        </div>
      </div>
      {items.map((item) => (
        <button
          key={item.id}
          tabIndex={0}
          className={classNames(styles.item, {
            [styles.active]: currentItem === item.id,
          })}
          onClick={() => setCurrentItem(item.id)}
        >
          <span>{item.label}</span>
          <div className={styles.itemContent}>
            <div className={styles.line} />
            <div className={styles.circle} />
          </div>
        </button>
      ))}
      <div className={classNames(styles.item, styles.placeholder)}>
        <span />
        <div className={styles.itemContent}>
          <div className={styles.line} />
        </div>
      </div>
    </div>
  )
}
