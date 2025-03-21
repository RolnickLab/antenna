import { useCollections } from 'data-services/hooks/collections/useCollections'
import { Select } from 'design-system/components/select/select'
import { useParams } from 'react-router-dom'

export const CollectionsPicker = ({
  onValueChange,
  showClear,
  value,
}: {
  onValueChange: (value?: string) => void
  showClear?: boolean
  value?: string
}) => {
  const { projectId } = useParams()
  const { collections = [], isLoading } = useCollections({
    projectId: projectId as string,
  })

  return (
    <Select
      loading={isLoading}
      onValueChange={onValueChange}
      options={collections.map((c) => ({
        value: c.id,
        label: c.name,
      }))}
      showClear={showClear}
      value={value}
    />
  )
}
