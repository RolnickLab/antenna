import { useSearchParams } from 'react-router-dom'

const DEFAULT_PAGINATION = {
  page: 0,
  perPage: 20,
}
const SEARCH_PARAM_KEY_PAGE = 'page'
const SEARCH_PARAM_KEY_PER_PAGE = 'per_page'

const useSearchParam = ({
  key,
  defaultValue,
}: {
  key: string
  defaultValue: number
}) => {
  const [searchParams, setSearchParams] = useSearchParams()

  const value = Number(searchParams.get(key) ?? defaultValue)

  const setValue = (value: number) => {
    const currentValue = searchParams.get(key)
    const newValue = `${value}`

    if (currentValue !== newValue) {
      searchParams.delete(key)
      searchParams.set(key, newValue)
      setSearchParams(searchParams)
    }
  }

  const clearValue = () => {
    if (searchParams.has(key)) {
      searchParams.delete(key)
    }
  }

  return { value, setValue, clearValue }
}

export const usePagination = () => {
  const { value: page, setValue: setPage } = useSearchParam({
    key: SEARCH_PARAM_KEY_PAGE,
    defaultValue: DEFAULT_PAGINATION.page,
  })

  const { value: perPage } = useSearchParam({
    key: SEARCH_PARAM_KEY_PER_PAGE,
    defaultValue: DEFAULT_PAGINATION.perPage,
  })

  return {
    pagination: {
      page,
      perPage,
    },
    setPrevPage: () => setPage(page - 1),
    setNextPage: () => setPage(page + 1),
  }
}
