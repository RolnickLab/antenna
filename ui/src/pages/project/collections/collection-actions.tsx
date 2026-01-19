import classNames from 'classnames'
import { usePopulateCollection } from 'data-services/hooks/collections/usePopulateCollection'
import { Collection } from 'data-services/models/collection'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, Loader2 } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const PopulateCollection = ({
  collection,
}: {
  collection: Collection
}) => {
  const { populateCollection, isLoading, error } = usePopulateCollection()

  return (
    <BasicTooltip
      asChild
      content={
        error ? 'Could not populate the collection, please retry.' : undefined
      }
    >
      <Button
        className={classNames({ 'text-destructive': error })}
        disabled={isLoading}
        onClick={() => populateCollection(collection.id)}
        size="small"
        variant="outline"
      >
        {error ? <AlertCircleIcon className="w-4 h-4" /> : null}
        <span>{translate(STRING.POPULATE)}</span>
        {isLoading ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : null}
      </Button>
    </BasicTooltip>
  )
}
