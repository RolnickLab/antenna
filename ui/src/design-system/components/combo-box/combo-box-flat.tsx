import classNames from 'classnames'
import { Command } from 'cmdk'
import { RefObject, useMemo, useState } from 'react'
import { Icon, IconType } from '../icon/icon'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import styles from './combo-box.module.scss'
import { Node, TreeItem } from './types'
import { buildTree } from './utils'

export const ComboBoxFlat = ({
  emptyLabel,
  inputRef,
  loading,
  nodes = [],
  searchString,
  selectedNodeId,
  onItemSelect,
  setSearchString,
}: {
  emptyLabel: string
  inputRef: RefObject<HTMLInputElement>
  loading?: boolean
  nodes?: Node[]
  searchString: string
  selectedNodeId?: string
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const [open, setOpen] = useState(false)
  const selectedLabel = nodes?.find((n) => n.id === selectedNodeId)?.label ?? ''
  const showLodingSpinner = loading && open
  const tree = useMemo(() => buildTree(nodes), [nodes])

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
        {tree.length ? (
          tree.map((treeItem) => (
            <ComboBoxFlatItem
              key={treeItem.id}
              treeItem={treeItem}
              onSelect={(treeItem) => {
                onItemSelect(treeItem.id)
                setSearchString(treeItem.label)
                inputRef?.current?.blur()
              }}
            />
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

const ComboBoxFlatItem = ({
  level = 0,
  treeItem,
  onSelect,
}: {
  level?: number
  treeItem: TreeItem
  onSelect: (treeItem: TreeItem) => void
}) => (
  <>
    <Command.Item
      className={styles.item}
      style={{ paddingLeft: `${level * 12}px` }}
      onSelect={() => onSelect(treeItem)}
    >
      <div className={styles.accessory}>
        {treeItem.children.length ? <Icon type={IconType.ToggleRight} /> : null}
      </div>
      <span>{treeItem.label}</span>
      <div className={styles.spacer} />
      {treeItem.details ? (
        <span className={styles.details}>{treeItem.details}</span>
      ) : null}
    </Command.Item>
    {treeItem.children.map((child) => (
      <ComboBoxFlatItem
        key={child.id}
        level={level + 1}
        treeItem={child}
        onSelect={onSelect}
      />
    ))}
  </>
)
