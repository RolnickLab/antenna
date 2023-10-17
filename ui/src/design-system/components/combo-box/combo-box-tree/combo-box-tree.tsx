import classNames from 'classnames'
import { Command } from 'cmdk'
import { RefObject, useMemo, useState } from 'react'
import { LoadingSpinner } from '../../loading-spinner/loading-spinner'
import styles from '../styles.module.scss'
import { buildTree } from './buildTree'
import { ComboBoxTreeItem } from './combo-box-tree-item'
import { Node } from './types'
import { useBottomAnchor } from './useBottomAnchor'

export const ComboBoxTree = ({
  containerRef,
  emptyLabel,
  inputRef,
  loading,
  nodes = [],
  searchString,
  selectedNodeId,
  selectedLabel = '',
  onItemSelect,
  setSearchString,
}: {
  containerRef: RefObject<HTMLDivElement>
  emptyLabel: string
  inputRef: RefObject<HTMLInputElement>
  loading?: boolean
  nodes?: Node[]
  searchString: string
  selectedNodeId?: string
  selectedLabel?: string
  onItemSelect: (id: string | number) => void
  setSearchString: (value: string) => void
}) => {
  const [open, setOpen] = useState(false)
  const tree = useMemo(() => buildTree(nodes), [nodes])
  const { top, left } = useBottomAnchor({
    containerRef,
    elementRef: inputRef,
    active: open,
  })

  return (
    <Command shouldFilter={false} className={styles.wrapper}>
      <Command.Input
        autoFocus
        className={classNames(styles.input, {
          [styles.loading]: loading,
        })}
        ref={inputRef}
        value={open ? searchString : selectedLabel}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onFocus={() => setOpen(true)}
        onValueChange={setSearchString}
      />
      {loading && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner size={12} />
        </div>
      )}
      <Command.List
        className={classNames(styles.content, styles.treeItems, {
          [styles.open]: open && searchString.length,
        })}
        style={{
          top,
          left,
        }}
      >
        {tree.length ? (
          tree.map((treeItem) => (
            <ComboBoxTreeItem
              key={treeItem.id}
              selectedNodeId={selectedNodeId}
              treeItem={treeItem}
              onSelect={(treeItem) => {
                onItemSelect(treeItem.id)
                setSearchString(treeItem.label)
                inputRef?.current?.blur()
              }}
            />
          ))
        ) : (
          <div className={classNames(styles.item, styles.empty)}>
            {emptyLabel}
          </div>
        )}
      </Command.List>
    </Command>
  )
}
