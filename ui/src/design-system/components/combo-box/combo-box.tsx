import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import classNames from 'classnames'
import { Command } from 'cmdk'
import { useState } from 'react'
import { Button } from '../button/button'
import styles from './combo-box.module.scss'

export const ComboBox = ({
  defaultOpen,
  emptyLabel,
  items = [],
  label,
  searchString,
  shouldFilter,
  onItemSelect,
  setSearchString,
}: {
  defaultOpen?: boolean
  emptyLabel: string
  items?: {
    id: string | number
    label: string
    details?: string
  }[]
  label: string
  searchString: string
  shouldFilter?: boolean
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>
        <Button label={label} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Content
        align="start"
        className={styles.content}
        side="bottom"
        sideOffset={8}
      >
        <DropdownMenu.Arrow className={styles.arrow} />
        <Command shouldFilter={shouldFilter}>
          <Command.Input
            autoFocus
            className={styles.input}
            value={searchString}
            onValueChange={setSearchString}
          />
          <Command.List>
            {items.length ? (
              items.map((item) => (
                <Command.Item
                  key={item.id}
                  onSelect={() => {
                    setOpen(false)
                    onItemSelect(item.id)
                  }}
                  className={styles.item}
                >
                  <span>{item.label}</span>
                  {item.details ? (
                    <span className={styles.details}>{item.details}</span>
                  ) : null}
                </Command.Item>
              ))
            ) : (
              <div className={classNames(styles.item, styles.empty)}>
                {emptyLabel}
              </div>
            )}
          </Command.List>
        </Command>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  )
}
