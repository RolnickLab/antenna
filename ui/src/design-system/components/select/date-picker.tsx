import { format } from 'date-fns'
import { AlertCircleIcon, Calendar as CalendarIcon } from 'lucide-react'
import { Button, Calendar, Popover } from 'nova-ui-kit'
import { useState } from 'react'

const dateToLabel = (date: Date) => {
  try {
    return format(date, 'yyyy-MM-dd')
  } catch {
    return 'Invalid date'
  }
}

export const DatePicker = ({
  error,
  onValueChange,
  value,
}: {
  error?: string
  onValueChange: (value?: string) => void
  value?: string
}) => {
  const [open, setOpen] = useState(false)
  const selected = value ? new Date(value) : undefined

  const triggerLabel = (() => {
    if (!value) {
      return 'Select a date'
    }

    return value
  })()

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between px-4 text-muted-foreground font-normal"
        >
          <>
            <span>{triggerLabel}</span>
            {selected && error ? (
              <AlertCircleIcon className="w-4 w-4 text-destructive" />
            ) : (
              <CalendarIcon className="w-4 w-4" />
            )}
          </>
        </Button>
      </Popover.Trigger>
      <Popover.Content className="w-auto p-0 overflow-hidden">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={(date) => {
            if (date) {
              onValueChange(dateToLabel(date))
            } else {
              onValueChange(undefined)
            }
            setOpen(false)
          }}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
