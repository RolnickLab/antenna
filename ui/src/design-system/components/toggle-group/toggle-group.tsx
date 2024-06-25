import * as _ToggleGroup from '@radix-ui/react-toggle-group'
import { Icon, IconTheme, IconType } from '../icon/icon'
import { Tooltip } from '../tooltip/tooltip'
import styles from './toggle-group.module.scss'

interface ToggleGroupProps {
  items: {
    icon: IconType
    value: string
    label: string
  }[]
  value?: string
  onValueChange: (value: string) => void
}

export const ToggleGroup = ({
  items,
  value,
  onValueChange,
}: ToggleGroupProps) => (
  <_ToggleGroup.Root
    type="single"
    value={value}
    onValueChange={onValueChange}
    className={styles.root}
  >
    {items.map((item) => (
      <Tooltip content={item.label}>
        <div className={styles.itemWrapper}>
          <_ToggleGroup.Item value={item.value} className={styles.item}>
            <Icon
              type={item.icon}
              theme={item.value === value ? IconTheme.Light : IconTheme.Primary}
            />
          </_ToggleGroup.Item>
        </div>
      </Tooltip>
    ))}
  </_ToggleGroup.Root>
)
