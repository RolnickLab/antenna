import * as _Select from '@radix-ui/react-select'
import React from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './select.module.scss'

interface SelectProps {
  label: string
  placeholder?: string
  options: {
    value: string
    label: string
  }[]
  description: string
}

export const Select = ({
  label,
  placeholder,
  options,
  description,
}: SelectProps) => (
  <div>
    <label className={styles.label}>{label}</label>
    <_Select.Root>
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
    <span className={styles.description}>{description}</span>
  </div>
)

interface SelectItemProps {
  label: string
  value: string
}

const SelectItem = React.forwardRef<HTMLDivElement, SelectItemProps>(
  ({ label, value, ...rest }, forwardedRef) => (
    <_Select.Item
      ref={forwardedRef}
      value={value}
      className={styles.selectItem}
      {...rest}
    >
      <_Select.ItemText>{label}</_Select.ItemText>
      <_Select.ItemIndicator className={styles.itemIndicator}>
        <Icon type={IconType.Checkmark} size={12} theme={IconTheme.Neutral} />
      </_Select.ItemIndicator>
    </_Select.Item>
  )
)
