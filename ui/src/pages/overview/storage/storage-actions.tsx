import { useSyncStorage } from 'data-services/hooks/storage-sources/useSyncStorage'
import { ConnectionStatus } from 'pages/deployment-details/connection-status/connection-status'
import { Status } from 'pages/deployment-details/connection-status/types'
import { useEffect, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'

export const SyncStorage = ({
  storageId: storageId,
}: {
  storageId: string
}) => {
  const { syncStorage, isLoading, isSuccess, error, validationError } =
    useSyncStorage()
  const [lastUpdated, setLastUpdated] = useState<Date>()

  useEffect(() => {
    syncStorage(storageId)
  }, [storageId])

  const status = (() => {
    if (isSuccess) {
      return Status.Connected
    }

    if (isLoading) {
      return Status.Connecting
    }

    return Status.NotConnected
  })()

  const tooltip = (() => {
    if (error) {
      return validationError?.detail || translate(STRING.UNKNOWN_ERROR)
    }

    if (lastUpdated) {
      return `${translate(STRING.LAST_UPDATED)} ${getFormatedDateTimeString({
        date: lastUpdated,
      })}`
    }
  })()

  return (
    <ConnectionStatus
      status={status}
      onRefreshClick={async () => {
        await syncStorage(storageId)
        setLastUpdated(new Date())
      }}
      tooltip={tooltip}
    />
  )
}
