import { usePopulateCollection } from 'data-services/hooks/collections/usePopulateCollection'
import { Collection } from 'data-services/models/collection'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { STRING, translate } from 'utils/language'

export const PopulateCollection = ({
  collection,
}: {
  collection: Collection
}) => {
  const { populateCollection, isLoading } = usePopulateCollection()

  return (
    <Button
      label={translate(STRING.POPULATE)}
      loading={isLoading}
      disabled={isLoading}
      theme={ButtonTheme.Success}
      onClick={() => populateCollection(collection.id)}
    />
  )
}
