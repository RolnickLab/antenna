import { usePopulateCollection } from 'data-services/hooks/collections/usePopulateCollection'
import { Collection } from 'data-services/models/collection'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const PopulateCollection = ({
  collection,
}: {
  collection: Collection
}) => {
  const [timestamp, setTimestamp] = useState<string>()
  const { populateCollection, isLoading } = usePopulateCollection()

  // When the collection is updated, we consider the population to be completed.
  // TODO: It would be better to inspect task status here, but we currently don't have this information.
  const isPopulating = isLoading || timestamp === collection.updatedAtDetailed

  return (
    <Button
      label={translate(STRING.POPULATE)}
      loading={isPopulating}
      disabled={isPopulating}
      theme={ButtonTheme.Success}
      onClick={() => {
        populateCollection(collection.id)
        setTimestamp(collection.updatedAtDetailed)
      }}
    />
  )
}
