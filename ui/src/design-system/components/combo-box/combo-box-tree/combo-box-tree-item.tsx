import classNames from 'classnames'
import { Command } from 'cmdk'
import { Icon, IconType } from '../../icon/icon'
import styles from '../styles.module.scss'
import { TreeItem } from './types'

export const ComboBoxTreeItem = ({
  level = 0,
  treeItem,
  selectedNodeId,
  onSelect,
}: {
  level?: number
  selectedNodeId?: string
  treeItem: TreeItem
  onSelect: (treeItem: TreeItem) => void
}) => {
  const isSelected = treeItem.id === selectedNodeId

  return (
    <>
      <Command.Item
        className={classNames(styles.item, { [styles.selected]: isSelected })}
        style={{ paddingLeft: `${level * 12}px` }}
        onSelect={() => onSelect(treeItem)}
      >
        <div className={styles.accessory}>
          {treeItem.children.length ? (
            <Icon type={IconType.ToggleDown} />
          ) : null}
        </div>
        <span>{treeItem.label}</span>
        <div className={styles.accessory}>
          {isSelected ? <Icon type={IconType.RadixCheck} /> : null}
        </div>
      </Command.Item>
      {treeItem.children.map((child) => (
        <ComboBoxTreeItem
          key={child.id}
          level={level + 1}
          selectedNodeId={selectedNodeId}
          treeItem={child}
          onSelect={onSelect}
        />
      ))}
    </>
  )
}
