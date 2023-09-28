import classNames from 'classnames'
import { Command } from 'cmdk'
import { useRef, useState } from 'react'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import styles from './combo-box.module.scss'

export const ComboBoxFlat = ({
  emptyLabel,
  items = [],
  loading,
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
  loading?: boolean
  searchString: string
  selectedItemId?: string
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const selectedLabel = items?.find((i) => i.id === selectedItemId)?.label ?? ''
  const showLodingSpinner = loading && open

  return (
    <Command shouldFilter={false} className={styles.wrapper}>
      <Command.Input
        autoFocus
        className={classNames(styles.input, {
          [styles.loading]: showLodingSpinner,
        })}
        ref={inputRef}
        value={open ? searchString : selectedLabel}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onFocus={() => setOpen(true)}
        onValueChange={setSearchString}
      />
      {showLodingSpinner && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner size={12} />
        </div>
      )}
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
