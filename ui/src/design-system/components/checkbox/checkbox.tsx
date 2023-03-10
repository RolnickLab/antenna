import * as _Checkbox from '@radix-ui/react-checkbox'
import { CheckIcon } from '@radix-ui/react-icons'
import classNames from 'classnames'
import styles from './checkbox.module.scss'

export enum CheckboxTheme {
  Default = 'default',
  Success = 'success',
  Alert = 'alert',
}

interface CheckboxProps {
  id: string
  label: string
  theme?: CheckboxTheme
  defaultChecked: boolean
}

export const Checkbox = ({
  id,
  label,
  theme = CheckboxTheme.Default,
  defaultChecked,
}: CheckboxProps) => {
  return (
    <div className={styles.wrapper}>
      <_Checkbox.Root
        id={id}
        className={styles.checkboxRoot}
        defaultChecked={defaultChecked}
      >
        <_Checkbox.Indicator className={styles.checkboxIndicator}>
          <CheckIcon />
        </_Checkbox.Indicator>
      </_Checkbox.Root>
      <label
        htmlFor={id}
        className={classNames(styles.label, {
          [styles.success]: theme === CheckboxTheme.Success,
          [styles.alert]: theme === CheckboxTheme.Alert,
        })}
      >
        {label}
      </label>
    </div>
  )
}
