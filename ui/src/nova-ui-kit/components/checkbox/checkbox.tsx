import * as _Checkbox from '@radix-ui/react-checkbox'
import classNames from 'classnames'
import { CheckIcon, MinusIcon } from 'lucide-react'
import styles from './checkbox.module.scss'

export enum CheckboxTheme {
  Default = 'default',
  Success = 'success',
  Alert = 'alert',
  Neutral = 'neutral',
}

interface CheckboxProps {
  checked: boolean | 'indeterminate'
  disabled?: boolean
  id?: string
  label?: string
  theme?: CheckboxTheme
  onCheckedChange?: (checked: boolean) => void
}

export const Checkbox = ({
  checked,
  disabled,
  id,
  label,
  theme = CheckboxTheme.Default,
  onCheckedChange,
}: CheckboxProps) => (
  <div className={styles.wrapper}>
    <_Checkbox.Root
      checked={checked}
      className={classNames(styles.checkboxRoot, {
        [styles.neutral]: theme === CheckboxTheme.Neutral,
      })}
      disabled={disabled}
      id={id}
      onCheckedChange={onCheckedChange}
    >
      <_Checkbox.Indicator className={styles.checkboxIndicator}>
        {checked === true && <CheckIcon className="w-4 h-4 text-background" />}
        {checked === 'indeterminate' && (
          <MinusIcon className="w-4 h-4 text-background" />
        )}
      </_Checkbox.Indicator>
    </_Checkbox.Root>
    {label && (
      <label
        htmlFor={id}
        className={classNames(styles.label, {
          [styles.success]: theme === CheckboxTheme.Success,
          [styles.alert]: theme === CheckboxTheme.Alert,
          [styles.neutral]: theme === CheckboxTheme.Neutral,
          [styles.disabled]: disabled,
        })}
      >
        {label}
      </label>
    )}
  </div>
)
