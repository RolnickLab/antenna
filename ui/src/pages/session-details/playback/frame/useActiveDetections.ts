import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

export const useActiveDetections = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeDetections, setActiveDetections] = useState<string[]>(
    searchParams.getAll('detection')
  )

  useEffect(() => {
    setSearchParams({ detection: activeDetections })
  }, [activeDetections])

  return { activeDetections, setActiveDetections }
}
