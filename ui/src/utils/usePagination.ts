import { useSearchParams } from 'react-router-dom'

const DEFAULT_PAGINATION = {
  page: 0,
  perPage: 20,
}
const SEARCH_PARAM_KEY_PAGE = 'page'

const useSearchParam = ({
  key,
  defaultValue,
}: {
  key: string
  defaultValue: number
}) => {
  const [searchParams, setSearchParams] = useSearchParams()
  const value = searchParams.has(key)
    ? Number(searchParams.get(key)) - 1
    : defaultValue

  const setValue = (value: number) => {
    const currentValue = searchParams.get(key)
    const newValue = `${value + 1}`

    if (currentValue !== newValue) {
      searchParams.delete(key)
      searchParams.set(key, newValue)
      setSearchParams(searchParams)
    }
  }

  const resetValue = () => {
    if (searchParams.has(key)) {
      searchParams.delete(key)
      setSearchParams(searchParams)
    }
  }

  return { value, setValue, resetValue }
}

export const usePagination = ({ perPage }: { perPage?: number } = {}) => {
  const {
    value: page,
    setValue: setPage,
    resetValue: resetPage,
  } = useSearchParam({
    key: SEARCH_PARAM_KEY_PAGE,
    defaultValue: DEFAULT_PAGINATION.page,
  })

  return {
    pagination: {
      page,
      perPage: perPage ?? DEFAULT_PAGINATION.perPage,
    },
    resetPage,
    setPage,
  }
}
