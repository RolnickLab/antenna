import * as _Select from '@radix-ui/react-select'
import classNames from 'classnames'
import { forwardRef } from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import styles from './select.module.scss'

export enum SelectTheme {
  Default = 'default',
  NeutralCompact = 'neutral-compact',
}

interface SelectProps {
  placeholderDisabled?: string
  label?: string
  loading?: boolean
  options?: {
    value: string
    label: string
  }[]
  placeholder?: string
  showClear?: boolean
  theme?: SelectTheme
  value?: string
  onValueChange: (value?: string) => void
}

export const Select = ({
  placeholderDisabled = 'Not available',
  label,
  loading,
  options = [],
  placeholder = 'Pick a value',
  showClear = true,
  theme = SelectTheme.Default,
  value,
  onValueChange,
}: SelectProps) => {
  const disabled = !loading && options.length === 0

  return (
    <div className={styles.wrapper}>
      {label && <label className={styles.label}>{label}</label>}
      <_Select.Root
        key={value}
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
      >
        <_Select.Trigger
          className={classNames(styles.selectTrigger, {
            [styles.disabled]: disabled,
            [styles.neutralCompact]: theme === SelectTheme.NeutralCompact,
          })}
        >
          <_Select.Value
            className={styles.value}
            placeholder={disabled ? placeholderDisabled : placeholder}
          />
          <_Select.Icon className={styles.selectIcon}>
            {loading ? (
              <LoadingSpinner size={12} />
            ) : (
              <Icon
                type={IconType.ToggleLeft}
                size={12}
                theme={
                  theme === SelectTheme.NeutralCompact
                    ? IconTheme.Light
                    : IconTheme.Neutral
                }
              />
            )}
          </_Select.Icon>
        </_Select.Trigger>
        <_Select.Portal>
          <_Select.Content
            className={styles.selectContent}
            position="popper"
            sideOffset={6}
          >
            <_Select.Viewport className={styles.selectViewport}>
              <_Select.Group>
                {options.map((option) => (
                  <SelectItem
                    key={option.value}
                    value={option.value}
                    label={option.label}
                  />
                ))}
              </_Select.Group>
            </_Select.Viewport>
          </_Select.Content>
        </_Select.Portal>
      </_Select.Root>
      {value && showClear && (
        <span className={styles.clear} onClick={() => onValueChange(undefined)}>
          Clear
        </span>
      )}
    </div>
  )
}

interface SelectItemProps {
  label: string
  value: string
}

const SelectItem = forwardRef<HTMLDivElement, SelectItemProps>(
  ({ label, value, ...rest }, forwardedRef) => (
    <_Select.Item
      ref={forwardedRef}
      value={value}
      className={styles.selectItem}
      {...rest}
    >
      <_Select.ItemText>{label}</_Select.ItemText>
      <_Select.ItemIndicator className={styles.itemIndicator}>
        <Icon type={IconType.RadixCheck} size={12} theme={IconTheme.Neutral} />
      </_Select.ItemIndicator>
    </_Select.Item>
  )
)
