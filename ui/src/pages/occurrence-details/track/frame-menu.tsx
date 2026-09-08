import { EllipsisVerticalIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { FrameAction } from './types'

export const FrameMenu = ({
  isFirstInTime,
  isOnlyFrame,
  onAction,
}: {
  isFirstInTime: boolean
  isOnlyFrame: boolean
  onAction: (action: FrameAction) => void
}) => {
  const [open, setOpen] = useState(false)

  const items: { action: FrameAction; disabled: boolean; label: string }[] = [
    {
      action: 'split',
      // Splitting at the earliest frame would move the whole occurrence, which the
      // API rejects.
      disabled: isFirstInTime,
      label: translate(STRING.TRACK_SPLIT_HERE),
    },
    {
      action: 'move',
      disabled: isOnlyFrame,
      label: translate(STRING.TRACK_MOVE_FRAME),
    },
    {
      action: 'remove',
      disabled: isOnlyFrame,
      label: translate(STRING.TRACK_REMOVE_FRAME),
    },
  ]

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          aria-label={translate(STRING.TRACK_FRAME_MENU)}
          size="icon"
          variant="ghost"
        >
          <EllipsisVerticalIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content align="start" className="w-auto p-1" side="right">
        <div className="flex flex-col items-stretch">
          {items.map((item) => (
            <Button
              disabled={item.disabled}
              key={item.action}
              onClick={() => {
                setOpen(false)
                onAction(item.action)
              }}
              size="small"
              variant="ghost"
            >
              <span className="w-full text-left">{item.label}</span>
            </Button>
          ))}
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
