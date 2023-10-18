import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import classNames from 'classnames'
import { Command } from 'cmdk'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { useState } from 'react'
import { Button } from '../../button/button'
import { IconType } from '../../icon/icon'
import styles from '../styles.module.scss'

export const ComboBoxSimple = ({
  emptyLabel,
  items = [],
  label,
  loading,
  searchString,
  onItemSelect,
  setSearchString,
}: {
  emptyLabel: string
  items?: {
    id: string | number
    label: string
  }[]
  label: string
  loading?: boolean
  searchString: string
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>
        <Button label={label} icon={IconType.RadixSearch} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Content
        align="start"
        className={styles.content}
        side="bottom"
        sideOffset={8}
      >
        <DropdownMenu.Arrow className={styles.arrow} />
        <Command shouldFilter={false} className={styles.wrapper}>
          <Command.Input
            autoFocus
            className={classNames(styles.input, {
              [styles.loading]: loading,
            })}
            value={searchString}
            onValueChange={setSearchString}
          />
          {loading && (
            <div className={styles.loadingWrapper}>
              <LoadingSpinner size={12} />
            </div>
          )}
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
