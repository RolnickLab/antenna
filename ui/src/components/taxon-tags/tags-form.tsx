import { useAssignTags } from 'data-services/hooks/taxa-tags/useAssignTags'
import { useTags } from 'data-services/hooks/taxa-tags/useTags'
import { Species, Tag } from 'data-services/models/species'
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { CheckIcon, Loader2Icon, PenIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

const CLOSE_TIMEOUT = 1000

export const TagsForm = ({ species }: { species: Species }) => {
  const { projectId } = useParams()
  const [open, setOpen] = useState(false)
  const [formValues, setFormValues] = useState(species.tags)
  const { tags = [] } = useTags({ projectId: projectId as string })
  const { assignTags, isLoading, isSuccess } = useAssignTags(species.id, () =>
    setTimeout(() => setOpen(false), CLOSE_TIMEOUT)
  )

  return (
    <Popover.Root
      open={open}
      onOpenChange={(open) => {
        setOpen(open)

        // Reset form values on open change
        setFormValues(species.tags)
      }}
    >
      <Popover.Trigger asChild>
        <Button size="icon" variant="ghost" disabled={tags.length === 0}>
          <PenIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content align="end" className="w-64">
        <div>
          <span className="block body-overline font-semibold text-muted-foreground mb-4">
            {translate(STRING.ENTITY_EDIT, {
              type: translate(STRING.FIELD_LABEL_TAGS).toLowerCase(),
            })}
          </span>
          <div className="grid gap-2 mb-8">
            {tags.map((tag) => (
              <FormRow
                key={tag.id}
                checked={formValues.some((t) => t.id === tag.id)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    setFormValues([...formValues, tag])
                  } else {
                    setFormValues(formValues.filter((t) => t.id !== tag.id))
                  }
                }}
                tag={tag}
              />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button
              onClick={() => setOpen(false)}
              size="small"
              variant="outline"
            >
              <span>{translate(STRING.CANCEL)}</span>
            </Button>
            <Button
              onClick={() =>
                assignTags({ projectId: projectId as string, tags: formValues })
              }
              size="small"
              variant="success"
            >
              <span>
                {isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}
              </span>
              {isSuccess ? (
                <CheckIcon className="w-4 h-4 ml-2" />
              ) : isLoading ? (
                <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
              ) : null}
            </Button>
          </div>
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}

const FormRow = ({
  checked,
  onCheckedChange,
  tag,
}: {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  tag: Tag
}) => (
  <div key={tag.id} className="flex items-center gap-2">
    <Checkbox
      id={`tag-${tag.id}`}
      checked={checked}
      onCheckedChange={onCheckedChange}
    />
    <label
      htmlFor={`tag-${tag.id}`}
      className="flex items-center gap-2 body-small"
    >
      <div className="w-2 h-2 rounded-full bg-primary" />
      {tag.name.toLowerCase()}
    </label>
  </div>
)
