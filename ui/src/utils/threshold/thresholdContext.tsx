import { ReactNode, createContext, useContext, useState } from 'react'
import { DEFAULT_THRESHOLD, THRESHOLD_STORAGE_KEY } from './constants'
import { ThresholdContextValues } from './types'

export const ThresholdContext = createContext<ThresholdContextValues>({
  defaultThreshold: DEFAULT_THRESHOLD,
  threshold: DEFAULT_THRESHOLD,
  setThreshold: () => {},
})

export const ThresholdContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const [threshold, setThreshold] = useState(() => {
    const value = localStorage.getItem(THRESHOLD_STORAGE_KEY)
    if (value?.length) {
      return Number(value)
    }
    return DEFAULT_THRESHOLD
  })

  return (
    <ThresholdContext.Provider
      value={{
        defaultThreshold: DEFAULT_THRESHOLD,
        threshold,
        setThreshold: (value: number) => {
          localStorage.setItem(THRESHOLD_STORAGE_KEY, `${threshold}`)
          setThreshold(value)
        },
      }}
    >
      {children}
    </ThresholdContext.Provider>
  )
}

export const useThreshold = () => useContext(ThresholdContext)
