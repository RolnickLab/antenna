import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { SettingsIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
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
    <BasicTooltip asChild content={translate(STRING.SETTINGS)}>
      <Popover.Trigger asChild>
        <Button className="shrink-0" size="icon" variant="ghost">
          <SettingsIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
    </BasicTooltip>
    <Popover.Content className={styles.wrapper} align="end" side="bottom">
      <div>
        <span className={styles.description}>
          {translate(STRING.TABLE_COLUMNS)}
        </span>
        <div className={styles.settings}>
          {columns.map((column) =>
            column.name.length ? (
              <Checkbox
                key={column.id}
                checked={columnSettings[column.id]}
                id={column.id}
                label={column.name}
                onCheckedChange={(checked) => {
                  onColumnSettingsChange({
                    ...columnSettings,
                    [column.id]: checked,
                  })
                }}
              />
            ) : null
          )}
        </div>
      </div>
    </Popover.Content>
  </Popover.Root>
)
