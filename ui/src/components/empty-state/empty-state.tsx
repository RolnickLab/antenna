import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'

export const EmptyState = () => {
  const { filters, activeFilters, clearFilter } = useFilters()

  return (
    <div className="flex flex-col gap-6 items-center py-24">
      <span className="body-base text-muted-foreground">
        {translate(
          activeFilters.length
            ? STRING.MESSAGE_NO_RESULTS_FOR_FILTERING
            : STRING.MESSAGE_NO_RESULTS
        )}
      </span>
      {activeFilters.length ? (
        <Button
          onClick={() => filters.map((filter) => clearFilter(filter.field))}
        >
          {translate(STRING.CLEAR_FILTERS)}
        </Button>
      ) : null}
    </div>
  )
}
