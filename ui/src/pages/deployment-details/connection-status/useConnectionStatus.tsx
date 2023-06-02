import { useEffect, useState } from 'react'
import { Status } from './types'

const getCurrentDateString = () => {
  const date = new Date()

  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/* TODO: Update when BE is supporting this */
export const useConnectionStatus = (path?: string) => {
  const [status, setStatus] = useState(
    path?.length ? Status.Connected : Status.NotConnected
  )
  const [lastUpdated, setLastUpdated] = useState<string>(getCurrentDateString())

  const refreshStatus = () => {
    setStatus(Status.Connecting)
    setTimeout(() => setStatus(Status.Connected), 2000)
  }

  useEffect(() => {
    setLastUpdated(getCurrentDateString())
  }, [status])

  return { status, refreshStatus, lastUpdated }
}
