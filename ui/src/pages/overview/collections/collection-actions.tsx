import { usePopulateCollection } from 'data-services/hooks/collections/usePopulateCollection'
import { Collection } from 'data-services/models/collection'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { STRING, translate } from 'utils/language'

export const PopulateCollection = ({
  collection,
}: {
  collection: Collection
}) => {
  const { populateCollection, isLoading, error } = usePopulateCollection()

  return (
    <Tooltip
      content={
        error ? 'Could not populate the collection, please retry.' : undefined
      }
    >
      <Button
        disabled={isLoading}
        label={translate(STRING.POPULATE)}
        icon={error ? IconType.Error : undefined}
        loading={isLoading}
        onClick={() => populateCollection(collection.id)}
        theme={error ? ButtonTheme.Error : undefined}
      />
    </Tooltip>
  )
}
