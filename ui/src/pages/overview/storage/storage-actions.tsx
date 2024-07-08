import { useSyncStorage } from 'data-services/hooks/storage-sources/useSyncStorage'
import { ConnectionStatus } from 'pages/deployment-details/connection-status/connection-status'
import { Status } from 'pages/deployment-details/connection-status/types'
import { useEffect, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'

export const SyncStorage = ({
  regexFilter,
  storageId,
  subDir,
  updatedAt,
}: {
  regexFilter?: string
  storageId: string
  subDir?: string
  updatedAt?: string
}) => {
  const [fullUri, setFullUri] = useState<string>()
  const { syncStorage, isLoading, isSuccess, error, validationError } =
    useSyncStorage()

  const [lastUpdated, setLastUpdated] = useState<Date>()

  const update = async () => {
    setFullUri(undefined)
    const result = await syncStorage({ id: storageId, subDir, regexFilter })
    setLastUpdated(new Date())
    setFullUri(result.data.full_uri)
  }

  useEffect(() => {
    update()
  }, [storageId, subDir, regexFilter, updatedAt])

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
        options: { second: true },
      })}`
    }
  })()

  return (
    <ConnectionStatus
      label={fullUri}
      status={status}
      onRefreshClick={update}
      tooltip={tooltip}
    />
  )
}
