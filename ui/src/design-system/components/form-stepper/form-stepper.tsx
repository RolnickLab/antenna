import classNames from 'classnames'
import styles from './form-stepper.module.scss'

type Item = {
  id: string
  label: string
}

interface FormStepperProps {
  items: Item[]
  currentItemId?: string
  setCurrentItemId: (item: string) => void
}

export const FormStepper = ({
  items,
  currentItemId,
  setCurrentItemId,
}: FormStepperProps) => (
  <div className={styles.wrapper}>
    <div className={classNames(styles.item, styles.placeholder)}>
      <span />
      <div className={styles.itemContent}>
        <div className={styles.line} />
      </div>
    </div>
    {items.map((item) => (
      <FormStepperItem
        key={item.id}
        active={currentItemId === item.id}
        item={item}
        onClick={() => setCurrentItemId(item.id)}
      />
    ))}
    <div className={classNames(styles.item, styles.placeholder)}>
      <span />
      <div className={styles.itemContent}>
        <div className={styles.line} />
      </div>
    </div>
  </div>
)

const FormStepperItem = ({
  active,
  item,
  onClick,
}: {
  active?: boolean
  item: Item
  onClick: () => void
}) => (
  <div
    role="button"
    key={item.id}
    tabIndex={0}
    className={classNames(styles.item, {
      [styles.active]: active,
    })}
    onClick={onClick}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onClick()
      }
    }}
  >
    <span>{item.label}</span>
    <div className={styles.itemContent}>
      <div className={styles.line} />
      <div className={styles.circle} />
    </div>
  </div>
)
