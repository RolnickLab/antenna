import classNames from 'classnames'
import { Command } from 'cmdk'
import { Icon, IconTheme, IconType } from '../../icon/icon'
import styles from '../styles.module.scss'
import { TreeItem } from 'components/taxon-search/types'

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
            <Icon type={IconType.ToggleDown} theme={IconTheme.Neutral} />
          ) : null}
        </div>
        <span>{treeItem.label}</span>
        {isSelected ? (
          <div className={styles.accessory}>
            <Icon type={IconType.RadixCheck} />{' '}
          </div>
        ) : null}
        <div className={styles.spacer} />
        {treeItem.details ? (
          <span className={styles.details}>{treeItem.details}</span>
        ) : null}
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
