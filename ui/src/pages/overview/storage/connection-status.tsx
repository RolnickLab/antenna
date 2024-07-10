import { FormRow } from 'components/form/layout/layout'
import { useSyncStorage } from 'data-services/hooks/storage-sources/useSyncStorage'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { Status } from 'pages/deployment-details/connection-status/types'
import { useEffect, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { StatusInfo } from './status-info/status-info'

export const ConnectionStatus = ({
  regex,
  showDetails,
  storageId,
  subdir,
  updatedAt,
}: {
  regex?: string
  showDetails?: boolean
  storageId: string
  subdir?: string
  updatedAt?: string
}) => {
  const { data, syncStorage, isLoading, error, validationError } =
    useSyncStorage()
  const [lastUpdated, setLastUpdated] = useState<Date>()

  const update = async () => {
    await syncStorage({ id: storageId, subdir, regex })
    setLastUpdated(new Date())
  }

  useEffect(() => {
    update()
  }, [storageId, subdir, regex, updatedAt])

  const status = (() => {
    if (data?.connection_successful) {
      if (subdir) {
        return data.prefix_exists ? Status.Connected : Status.NotConnected
      } else {
        return Status.Connected
      }
    }

    if (isLoading) {
      return Status.Connecting
    }

    return Status.NotConnected
  })()

  const label = (() => {
    if (data?.connection_successful) {
      if (subdir) {
        return data.prefix_exists
          ? translate(STRING.CONNECTED)
          : 'Problem with connection'
      } else {
        return translate(STRING.CONNECTED)
      }
    }

    if (isLoading) {
      return translate(STRING.CONNECTING)
    }

    return translate(STRING.NOT_CONNECTED)
  })()

  const tooltip = (() => {
    // Show error info from request info
    if (error) {
      return validationError?.detail || translate(STRING.UNKNOWN_ERROR)
    }

    // Show error info from response data
    if (data?.error_code || data?.error_message) {
      return data?.error_message || translate(STRING.UNKNOWN_ERROR)
    }

    // Show info about sub directory
    if (subdir || regex) {
      if (data?.connection_successful && !data.prefix_exists) {
        return `Connection was successful but the prefix was not recognized.`
      }
    }

    if (lastUpdated) {
      return `${translate(STRING.LAST_UPDATED)} ${getFormatedDateTimeString({
        date: lastUpdated,
        options: { second: true },
      })}`
    }
  })()

  return (
    <FormRow>
      <InputContent label="Connection status">
        <StatusInfo label={label} status={status} tooltip={tooltip} />
      </InputContent>
      <InputValue label="Full URI" value={data?.full_uri} />
      {showDetails && (
        <>
          <InputValue label="Latency" value={data?.latency} />
          <InputValue label="Files checked" value={data?.files_checked} />
          {data?.first_file_found && (
            <InputContent label="First file found">
              <a href={data?.first_file_found} rel="noreferrer" target="_blank">
                <img style={{ maxWidth: '100%' }} src={data.first_file_found} />
              </a>
            </InputContent>
          )}
        </>
      )}
    </FormRow>
  )
}
