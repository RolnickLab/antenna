import * as _ToggleGroup from '@radix-ui/react-toggle-group'
import classNames from 'classnames'
import { Icon, IconTheme, IconType } from '../icon/icon'
import { BasicTooltip } from '../tooltip/basic-tooltip'
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
    {items.map((item, index) => {
      const isActive = item.value === value

      return (
        <BasicTooltip key={item.value} asChild content={item.label}>
          <_ToggleGroup.Item
            value={item.value}
            className={classNames(styles.item, {
              [styles.active]: isActive,
              [styles.first]: index === 0,
              [styles.last]: index === items.length - 1,
            })}
          >
            <Icon
              type={item.icon}
              theme={isActive ? IconTheme.Light : IconTheme.Primary}
            />
          </_ToggleGroup.Item>
        </BasicTooltip>
      )
    })}
  </_ToggleGroup.Root>
)
