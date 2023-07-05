import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

export const useActiveOccurrences = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeOccurrences, setActiveOccurrences] = useState<string[]>(
    searchParams.getAll('occurrence')
  )

  useEffect(() => {
    setSearchParams({ occurrence: activeOccurrences })
  }, [activeOccurrences])

  return { activeOccurrences, setActiveOccurrences }
}
