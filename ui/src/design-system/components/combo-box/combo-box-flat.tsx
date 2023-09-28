import classNames from 'classnames'
import { Command } from 'cmdk'
import { useRef, useState } from 'react'
import styles from './combo-box.module.scss'

export const ComboBoxFlat = ({
  emptyLabel,
  items = [],
  searchString,
  selectedItemId,
  onItemSelect,
  setSearchString,
}: {
  emptyLabel: string
  items?: {
    id: string | number
    label: string
    details?: string
  }[]
  searchString: string
  selectedItemId?: string
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const selectedLabel = items?.find((i) => i.id === selectedItemId)?.label ?? ''

  return (
    <Command shouldFilter={false} className={styles.wrapper}>
      <Command.Input
        autoFocus
        className={styles.input}
        ref={inputRef}
        value={open ? searchString : selectedLabel}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onFocus={() => setOpen(true)}
        onValueChange={setSearchString}
      />
      <Command.List
        className={classNames(styles.items, { [styles.open]: open })}
      >
        {items.length ? (
          items.map((item) => (
            <Command.Item
              key={item.id}
              className={styles.item}
              onSelect={() => {
                onItemSelect(item.id)
                setSearchString(item.label)
                inputRef?.current?.blur()
              }}
            >
              <span>{item.label}</span>
              {item.details ? (
                <span className={styles.details}>{item.details}</span>
              ) : null}
            </Command.Item>
          ))
        ) : searchString.length ? (
          <div className={classNames(styles.item, styles.empty)}>
            {emptyLabel}
          </div>
        ) : null}
      </Command.List>
    </Command>
  )
}
