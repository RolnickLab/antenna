import { useEffect, useState } from 'react'

export const useWindowSize = () => {
  const [windowSize, setWindowSize] = useState([
    Math.max(document.documentElement.clientWidth, window.innerWidth),
    Math.max(document.documentElement.clientHeight, window.innerHeight),
  ])

  useEffect(() => {
    const windowSizeHandler = () =>
      setWindowSize([window.innerWidth, window.innerHeight])

    window.addEventListener('resize', windowSizeHandler)

    return () => {
      window.removeEventListener('resize', windowSizeHandler)
    }
  }, [])

  return windowSize
}
