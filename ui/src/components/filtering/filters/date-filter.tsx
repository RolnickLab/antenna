import { format } from 'date-fns'
import { Calendar as CalendarIcon } from 'lucide-react'
import { Button, Calendar, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { FilterProps } from './types'

const dateToLabel = (date: Date) => format(date, 'yyyy-MM-dd')

export const DateFilter = ({ value, onAdd, onClear }: FilterProps) => {
  const [open, setOpen] = useState(false)
  const selected = value ? new Date(value) : undefined

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-72 justify-between text-muted-foreground font-normal"
        >
          <>
            <span>{selected ? dateToLabel(selected) : 'Select a date'}</span>
            <CalendarIcon className="w-4 w-4" />
          </>
        </Button>
      </Popover.Trigger>
      <Popover.Content className="w-auto p-0 overflow-hidden">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={(date) => {
            if (date) {
              onAdd(dateToLabel(date))
            } else {
              onClear()
            }
            setOpen(false)
          }}
        />
      </Popover.Content>
    </Popover.Root>
  )
}