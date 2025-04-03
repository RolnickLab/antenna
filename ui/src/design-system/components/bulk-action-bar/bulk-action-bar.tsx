import { XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { ReactNode } from 'react'
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
    <span className="pt-0.5 body-small font-medium text-muted-foregroud">
      {selectedItems.length} selected
    </span>
    {children}
    <Button onClick={onClear} size="icon" variant="ghost">
      <XIcon className="w-4 h-4" />
    </Button>
  </div>
)
