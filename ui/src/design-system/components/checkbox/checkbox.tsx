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
  checked?: boolean | 'indeterminate'
  defaultChecked?: boolean
  id?: string
  label?: string
  theme?: CheckboxTheme
  onCheckedChange?: (checked: boolean) => void
}

export const Checkbox = ({
  checked,
  defaultChecked,
  id,
  label,
  theme = CheckboxTheme.Default,
  onCheckedChange,
}: CheckboxProps) => (
  <div className={styles.wrapper}>
    <_Checkbox.Root
      className={styles.checkboxRoot}
      checked={checked}
      defaultChecked={defaultChecked}
      id={id}
      onCheckedChange={onCheckedChange}
    >
      <_Checkbox.Indicator className={styles.checkboxIndicator}>
        {checked === true && (
          <Icon type={IconType.RadixCheck} theme={IconTheme.Light} />
        )}
        {checked === 'indeterminate' && (
          <Icon type={IconType.RadixMinus} theme={IconTheme.Light} />
        )}
      </_Checkbox.Indicator>
    </_Checkbox.Root>
    {label && (
      <label
        htmlFor={id}
        className={classNames(styles.label, {
          [styles.success]: theme === CheckboxTheme.Success,
          [styles.alert]: theme === CheckboxTheme.Alert,
        })}
      >
        {label}
      </label>
    )}
  </div>
)
