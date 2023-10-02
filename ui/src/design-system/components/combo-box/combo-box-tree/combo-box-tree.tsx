import classNames from 'classnames'
import { Command } from 'cmdk'
import { RefObject, useMemo, useState } from 'react'
import { LoadingSpinner } from '../../loading-spinner/loading-spinner'
import styles from '../styles.module.scss'
import { buildTree } from './buildTree'
import { ComboBoxTreeItem } from './combo-box-tree-item'
import { sortTree } from './sortTree'
import { Node } from './types'

export const ComboBoxTree = ({
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
  const tree = useMemo(() => {
    const tree = buildTree(nodes)
    const sortedTree = sortTree(tree)
    return sortedTree
  }, [nodes])

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
          [styles.open]: open,
        })}
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
        ) : searchString.length ? (
          <div className={classNames(styles.item, styles.empty)}>
            {emptyLabel}
          </div>
        ) : null}
      </Command.List>
    </Command>
  )
}
