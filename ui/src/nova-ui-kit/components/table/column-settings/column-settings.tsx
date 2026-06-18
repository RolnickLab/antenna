import { Columns3CogIcon } from 'lucide-react'
import { BasicTooltip, Button, Checkbox, Popover } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

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
    <BasicTooltip asChild content={translate(STRING.TABLE_COLUMNS)}>
      <Popover.Trigger asChild>
        <Button
          aria-label={translate(STRING.TABLE_COLUMNS)}
          className="shrink-0"
          size="icon"
          variant="outline"
        >
          <Columns3CogIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
    </BasicTooltip>
    <Popover.Content className="grid gap-4" align="end" side="bottom">
      <span className="body-base font-semibold text-muted-foreground">
        {translate(STRING.TABLE_COLUMNS)}
      </span>
      <div className="grid gap-2">
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
    </Popover.Content>
  </Popover.Root>
)
