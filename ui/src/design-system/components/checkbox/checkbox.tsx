import * as _Checkbox from '@radix-ui/react-checkbox'
import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import styles from './checkbox.module.scss'

export enum CheckboxTheme {
  Default = 'default',
  Success = 'success',
  Alert = 'alert',
  Neutral = 'neutral',
}

interface CheckboxProps {
  id: string
  label?: string
  theme?: CheckboxTheme
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
  defaultChecked?: boolean
}

export const Checkbox = ({
  id,
  label,
  theme = CheckboxTheme.Default,
  checked,
  onCheckedChange,
  defaultChecked,
}: CheckboxProps) => {
  return (
    <div className={styles.wrapper}>
      <_Checkbox.Root
        id={id}
        className={classNames(styles.checkboxRoot, {
          [styles.neutral]: theme === CheckboxTheme.Neutral,
        })}
        checked={checked}
        defaultChecked={defaultChecked}
        onCheckedChange={onCheckedChange}
      >
        <_Checkbox.Indicator className={styles.checkboxIndicator}>
          <Icon type={IconType.RadixCheck} theme={IconTheme.Light} />
        </_Checkbox.Indicator>
      </_Checkbox.Root>
      <label
        htmlFor={id}
        className={classNames(styles.label, {
          [styles.success]: theme === CheckboxTheme.Success,
          [styles.alert]: theme === CheckboxTheme.Alert,
          [styles.neutral]: theme === CheckboxTheme.Neutral,
        })}
      >
        {label}
      </label>
    </div>
  )
}
