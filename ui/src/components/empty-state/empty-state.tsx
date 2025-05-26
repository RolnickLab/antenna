import { Button } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'

export const EmptyState = () => {
  const { filters, activeFilters, clearFilter } = useFilters()
  const { pagination, resetPage } = usePagination()

  if (pagination.page) {
    return (
      <Container>
        <p>{translate(STRING.MESSAGE_NO_RESULTS_FOR_PAGE)}</p>
        <Button onClick={() => resetPage()}>
          {translate(STRING.RESET_PAGE)}
        </Button>
      </Container>
    )
  }

  if (activeFilters.length) {
    return (
      <Container>
        <p>{translate(STRING.MESSAGE_NO_RESULTS_FOR_FILTERING)}</p>
        <Button
          onClick={() => filters.map((filter) => clearFilter(filter.field))}
        >
          {translate(STRING.CLEAR_FILTERS)}
        </Button>
      </Container>
    )
  }

  return (
    <Container>
      <p>{translate(STRING.MESSAGE_NO_RESULTS)}</p>
    </Container>
  )
}

const Container = ({ children }: { children: ReactNode }) => (
  <div className="flex flex-col gap-6 items-center py-24">{children}</div>
)
