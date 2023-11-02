import * as _Select from '@radix-ui/react-select'
import { forwardRef } from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './select.module.scss'

interface SelectProps {
  description?: string
  label?: string
  options?: {
    value: string
    label: string
  }[]
  placeholder?: string
  value?: string
  onValueChange: (value: string) => void
}

export const Select = ({
  description,
  label,
  options = [],
  placeholder,
  value,
  onValueChange,
}: SelectProps) => (
  <div>
    {label && <label className={styles.label}>{label}</label>}
    <_Select.Root value={value} onValueChange={onValueChange}>
      <_Select.Trigger className={styles.selectTrigger}>
        <_Select.Value placeholder={placeholder} />
        <_Select.Icon className={styles.selectIcon}>
          <Icon
            type={IconType.ToggleLeft}
            size={12}
            theme={IconTheme.Neutral}
          />
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
    {description?.length && (
      <span className={styles.description}>{description}</span>
    )}
  </div>
)

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
