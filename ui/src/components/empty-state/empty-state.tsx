import { Button } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'

export const EmptyState = ({ children }: { children?: ReactNode }) => {
  const { filters, activeFilters, clearFilter } = useFilters()
  const { pagination, resetPage } = usePagination()

  if (pagination.page) {
    return (
      <Container message={translate(STRING.MESSAGE_NO_RESULTS_FOR_PAGE)}>
        <Button onClick={() => resetPage()}>
          {translate(STRING.RESET_PAGE)}
        </Button>
      </Container>
    )
  }

  if (activeFilters.length) {
    return (
      <Container message={translate(STRING.MESSAGE_NO_RESULTS_FOR_FILTERING)}>
        <Button
          onClick={() => filters.map((filter) => clearFilter(filter.field))}
        >
          {translate(STRING.CLEAR_FILTERS)}
        </Button>
      </Container>
    )
  }

  return (
    <Container message={translate(STRING.MESSAGE_NO_RESULTS_TO_SHOW)}>
      {children}
    </Container>
  )
}

const Container = ({
  message,
  children,
}: {
  message: string
  children: ReactNode
}) => (
  <div className="flex flex-col items-center pt-32">
    <h1 className="mb-8 heading-large">No results</h1>
    <p className="text-center body-large mb-16">{message}</p>
    <div className="flex flex-col items-center gap-8">{children}</div>
  </div>
)
