import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import * as Popover from 'design-system/components/popover/popover'
import { STRING, translate } from 'utils/language'
import styles from './column-settings.module.scss'

interface ColumnSettingsProps {
  columns: { id: string; name: string }[]
  columnSettings: { [id: string]: boolean }
  onColumnSettingsChange: (columnSettings: { [id: string]: boolean }) => void
}

export const ColumnSettings = ({
  columns,
  columnSettings,
  onColumnSettingsChange,
}: ColumnSettingsProps) => (
  <Popover.Root>
    <Popover.Trigger>
      <IconButton icon={IconType.Options} />
    </Popover.Trigger>
    <Popover.Content
      ariaCloselabel={translate(STRING.CLOSE)}
      align="start"
      side="left"
    >
      <div className={styles.wrapper}>
        <span className={styles.description}>
          {translate(STRING.SELECT_COLUMNS)}
        </span>
        <div className={styles.settings}>
          {columns.map((column) => (
            <Checkbox
              key={column.id}
              id={column.id}
              label={column.name}
              onCheckedChange={(checked) => {
                onColumnSettingsChange({
                  ...columnSettings,
                  [column.id]: checked,
                })
              }}
              defaultChecked={columnSettings[column.id]}
            />
          ))}
        </div>
      </div>
    </Popover.Content>
  </Popover.Root>
)
