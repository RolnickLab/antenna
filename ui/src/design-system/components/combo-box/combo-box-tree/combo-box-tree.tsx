import classNames from 'classnames'
import { Command } from 'cmdk'
import { buildTree } from 'components/taxon-search/buildTree'
import { Node } from 'components/taxon-search/types'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { RefObject, useMemo, useState } from 'react'
import { LoadingSpinner } from '../../loading-spinner/loading-spinner'
import styles from '../styles.module.scss'
import { ComboBoxTreeItem } from './combo-box-tree-item'
import { useBottomAnchor } from './useBottomAnchor'

/** Deprecated in favor of /components/taxon-search/ */
export const ComboBoxTree = ({
  autoFocus = true,
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
  autoFocus?: boolean
  containerRef: RefObject<HTMLDivElement>
  emptyLabel: string
  inputRef: RefObject<HTMLInputElement>
  loading?: boolean
  nodes?: Node[]
  searchString: string
  selectedNodeId?: string
  selectedLabel?: string
  onItemSelect: (id: string | number | undefined) => void
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
        placeholder="Search taxonomy"
        autoFocus={autoFocus}
        className={styles.input}
        ref={inputRef}
        value={open ? searchString : selectedLabel}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onFocus={() => setOpen(true)}
        onValueChange={setSearchString}
      />
      <div className={styles.accessoryWrapper}>
        {open && loading && <LoadingSpinner size={12} />}
        {!open && selectedNodeId && (
          <IconButton
            icon={IconType.Cross}
            theme={IconButtonTheme.Plain}
            onClick={() => {
              onItemSelect(undefined)
              setSearchString('')
              inputRef?.current?.blur()
            }}
          />
        )}
      </div>
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
