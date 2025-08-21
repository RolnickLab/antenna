import { useUpdateSpecies } from 'data-services/hooks/species/useUpdateSpecies'
import { Species } from 'data-services/models/species'
import { CheckIcon, Loader2Icon, PenIcon } from 'lucide-react'
import { Button, Input, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

const CLOSE_TIMEOUT = 1000

export const SpeciesNameForm = ({ species }: { species: Species }) => {
  const { projectId } = useParams()
  const [open, setOpen] = useState(false)
  const [formValue, setFormValue] = useState(species.name)
  const { updateSpecies, isLoading, isSuccess } = useUpdateSpecies(
    species.id,
    () => setTimeout(() => setOpen(false), CLOSE_TIMEOUT)
  )

  return (
    <Popover.Root
      open={open}
      onOpenChange={(open) => {
        setOpen(open)

        // Reset form values on open change
        setFormValue(species.name)
      }}
    >
      <Popover.Trigger asChild>
        <Button size="icon" variant="ghost">
          <PenIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content align="end" className="w-64">
        <div>
          <span className="block body-overline font-semibold text-muted-foreground mb-4">
            {translate(STRING.ENTITY_EDIT, {
              type: translate(STRING.FIELD_LABEL_NAME).toLowerCase(),
            })}
          </span>
          <Input
            className="mb-8"
            value={formValue}
            onChange={(e) => setFormValue(e.currentTarget.value)}
          />
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
                updateSpecies({
                  fieldValues: { name: formValue },
                  projectId: projectId as string,
                })
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
