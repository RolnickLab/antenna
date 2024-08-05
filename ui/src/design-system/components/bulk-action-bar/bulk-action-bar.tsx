import { ReactNode } from 'react'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import styles from './bulk-action-bar.module.scss'

interface BulkActionBarProps {
  children: ReactNode
  selectedItems: string[]
  onClear: () => void
}

export const BulkActionBar = ({
  children,
  selectedItems,
  onClear,
}: BulkActionBarProps) => (
  <div className={styles.wrapper}>
    <span className={styles.infoLabel}>{selectedItems.length} selected</span>
    {children}
    <IconButton
      icon={IconType.Cross}
      theme={IconButtonTheme.Plain}
      onClick={onClear}
    />
  </div>
)
