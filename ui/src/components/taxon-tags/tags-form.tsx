import classNames from 'classnames'
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { PenIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { AVAILABLE_TAGS, TAG_CLASSES } from './constants'
import { TagData } from './types'

export const TagsForm = ({
  tags,
  onTagsChange,
}: {
  tags: TagData[]
  onTagsChange: (tags: TagData[]) => void
}) => (
  <Popover.Root>
    <Popover.Trigger asChild>
      <Button size="icon" variant="ghost">
        <PenIcon className="w-4 h-4" />
      </Button>
    </Popover.Trigger>
    <Popover.Content align="end" className="w-auto">
      <div className="grid gap-2">
        {AVAILABLE_TAGS.map((tag) => (
          <FormRow
            key={tag.value}
            onTagsChange={onTagsChange}
            tag={tag}
            tags={tags}
          />
        ))}
      </div>
    </Popover.Content>
  </Popover.Root>
)

const FormRow = ({
  tag,
  tags,
  onTagsChange,
}: {
  tag: TagData
  tags: TagData[]
  onTagsChange: (tags: TagData[]) => void
}) => {
  const checked = tags.some((t) => t.value === tag.value)

  return (
    <div key={tag.value} className="flex items-center gap-2">
      <Checkbox
        id={tag.value}
        checked={checked}
        onCheckedChange={(checked) => {
          /* TODO: Replace with API call */
          if (checked) {
            onTagsChange([...tags, tag])
          } else {
            onTagsChange(tags.filter((t) => t.value !== tag.value))
          }
        }}
      />
      <div
        className={classNames(
          'w-4 h-4 rounded-full bg-primary',
          TAG_CLASSES[tag.value]
        )}
      />
      <label htmlFor={tag.value} className="body-small">
        {tag.label.toLowerCase()}
      </label>
    </div>
  )
}
