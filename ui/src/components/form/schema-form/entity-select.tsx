import { API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from 'data-services/hooks/auth/useAuthorizedQuery'
import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

const PAGE_SIZE = 100

interface EntityOption {
  id: string
  label: string
}

const getLabel = (record: any): string => {
  const name = record.name ?? `${record.id}`
  return typeof record.source_images_count === 'number'
    ? `${name} (${record.source_images_count.toLocaleString()})`
    : name
}

export const EntitySelect = ({
  entity,
  entityFilters,
  projectId,
  value,
  onValueChange,
}: {
  entity: string
  entityFilters?: { [key: string]: string | number | boolean }
  projectId: string
  value?: string
  onValueChange: (value: string | undefined, label?: string) => void
}) => {
  const params = new URLSearchParams({
    project_id: projectId,
    limit: `${PAGE_SIZE}`,
    ...Object.fromEntries(
      Object.entries(entityFilters ?? {}).map(([k, v]) => [k, `${v}`])
    ),
  })
  const { data, isLoading } = useAuthorizedQuery<{ results: any[] }>({
    queryKey: [entity, 'options', params.toString()],
    url: `${API_URL}/${entity}/?${params.toString()}`,
  })
  const options: EntityOption[] = (data?.results ?? []).map((record) => ({
    id: `${record.id}`,
    label: getLabel(record),
  }))
  const selected = options.some((option) => option.id === value) ? value : ''

  return (
    <Select.Root
      key={selected}
      disabled={isLoading || options.length === 0}
      onValueChange={(id) =>
        onValueChange(id, options.find((option) => option.id === id)?.label)
      }
      value={selected}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {options.map((option) => (
          <Select.Item key={option.id} value={option.id}>
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
