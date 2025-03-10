import { useCollections } from 'data-services/hooks/collections/useCollections'
import { Select } from 'design-system/components/select/select'
import { useParams } from 'react-router-dom'

export const CollectionsPicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { collections = [], isLoading } = useCollections({
    projectId: projectId as string,
  })

  return (
    <Select
      loading={isLoading}
      options={collections.map((c) => ({
        value: c.id,
        label: c.name,
      }))}
      value={value}
      onValueChange={onValueChange}
    />
  )
}
