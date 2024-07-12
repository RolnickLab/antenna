import { Button, ButtonTheme } from '../button/button'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import styles from './bulk-action-bar.module.scss'

interface BulkActionBarProps {
  selectedItems: string[]
  onClear: () => void
}

export const BulkActionBar = ({
  selectedItems,
  onClear,
}: BulkActionBarProps) => {
  return (
    <div className={styles.wrapper}>
      <span className={styles.infoLabel}>{selectedItems.length} selected</span>
      <Button label="Agree" theme={ButtonTheme.Success} />
      <IconButton icon={IconType.Options} />
      <IconButton
        icon={IconType.Cross}
        theme={IconButtonTheme.Plain}
        onClick={onClear}
      />
    </div>
  )
}
