import * as _Checkbox from '@radix-ui/react-checkbox'
import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
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
  defaultChecked?: boolean
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
          <Icon type={IconType.Checkmark} theme={IconTheme.Light} />
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
