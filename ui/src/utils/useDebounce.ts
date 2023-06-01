import _ from 'lodash'
import { useCallback, useState } from 'react'

export const useDebounce = <T>(value: T, delay: number): T => {
  const [debouncedValue, _setDebouncedValue] = useState<T>(value)
  const setDebouncedValue = useCallback(_.debounce(_setDebouncedValue, delay), [
    _setDebouncedValue,
  ])
  setDebouncedValue(value)

  return debouncedValue
}
