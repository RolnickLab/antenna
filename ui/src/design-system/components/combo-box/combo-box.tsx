import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Command } from 'cmdk'
import { useState } from 'react'
import { Button } from '../button/button'
import styles from './combo-box.module.scss'

export const ComboBox = ({
  emptyLabel,
  items = [],
  label,
  searchString,
  shouldFilter,
  onItemSelect,
  setSearchString,
}: {
  emptyLabel: string
  items?: {
    id: string | number
    label: string
  }[]
  label: string
  searchString: string
  shouldFilter?: boolean
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const [open, setOpen] = useState(false)

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
                  {item.label}
                </Command.Item>
              ))
            ) : (
              <div className={styles.item}>{emptyLabel}</div>
            )}
          </Command.List>
        </Command>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  )
}
