import { useEntities } from 'data-services/hooks/entities/useEntities'
import { XIcon } from 'lucide-react'
import { Button, Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

// TODO: Move to src/components, this is not a design system component
export const EntityPicker = ({
  clearable,
  collection,
  value: _value,
  onValueChange,
}: {
  clearable?: boolean
  collection: string
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { entities = [], isLoading } = useEntities(collection, {
    projectId: projectId as string,
  })
  const value = entities.some((e) => e.id === _value) ? _value : ''

  const select = (
    <Select.Root
      key={value}
      disabled={isLoading || entities.length === 0}
      onValueChange={onValueChange}
      value={value}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {entities.map((e) => (
          <Select.Item key={e.id} value={e.id}>
            {e.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )

  if (!clearable) {
    return select
  }

  return (
    <div className="flex items-center justify-between gap-2">
      {select}
      {_value && (
        <Button
          aria-label={translate(STRING.CLEAR)}
          className="shrink-0 text-muted-foreground"
          onClick={() => onValueChange()}
          size="icon"
          variant="ghost"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      )}
    </div>
  )
}
