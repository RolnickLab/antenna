import { FormRow } from 'components/form/layout/layout'
import { useTestStorageConnection } from 'data-services/hooks/storage-sources/useTestStorageConnection'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import * as Wizard from 'design-system/components/wizard/wizard'
import { useEffect, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { StatusInfo } from './status-info/status-info'
import { Status } from './status-info/types'
import styles from './storage.module.scss'

export const ConnectionStatus = ({
  regex,
  showDetails,
  storageId,
  subdir,
  updatedAt,
  onConnectionChange,
}: {
  regex?: string
  showDetails?: boolean
  storageId: string
  subdir?: string
  updatedAt?: string
  onConnectionChange?: (isConnected: boolean) => void
}) => {
  const { data, testStorageConnection, isLoading, error, validationError } =
    useTestStorageConnection()
  const [lastUpdated, setLastUpdated] = useState<Date>()

  const update = async () => {
    try {
      await testStorageConnection({ id: storageId, subdir, regex })
    } catch {
      // Error handled in hook
    }

    setLastUpdated(new Date())
  }

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

  const details = (() => {
    // Show error info from request info
    if (error) {
      if (validationError?.detail) {
        return validationError.detail
      }

      if (Object.keys(error.response?.data ?? []).includes('subdir')) {
        return 'Please provide a valid sub directory.'
      }

      return translate(STRING.UNKNOWN_ERROR)
    }

    // Show error info from response data
    if (data?.error_code || data?.error_message) {
      return data?.error_message || translate(STRING.UNKNOWN_ERROR)
    }

    if (lastUpdated) {
      return `${translate(STRING.LAST_UPDATED)} ${getFormatedDateTimeString({
        date: lastUpdated,
        options: { second: true },
      })}`
    }
  })()

  useEffect(() => {
    update()
  }, [storageId, subdir, regex, updatedAt])

  useEffect(() => {
    onConnectionChange?.(status === Status.Connected)
  }, [status])

  return (
    <div className={styles.connectionStatus}>
      <Wizard.Root className={styles.wizardRoot}>
        <Wizard.Item value="connection-status">
          <Wizard.Trigger
            title={label}
            className={styles.wizardTrigger}
            showToggle
          >
            <StatusInfo status={status} tooltip={details} />
          </Wizard.Trigger>
          <Wizard.Content className={styles.wizardContent}>
            <FormRow>
              <InputValue label="Connection details" value={details} />
              <InputValue label="Full URI" value={data?.full_uri} />
              <InputValue label="Latency (s)" value={data?.latency} />
              <InputValue label="Total time (s)" value={data?.total_time} />
              {showDetails ? (
                <>
                  {data?.first_file_found ? (
                    <InputContent label="First file found">
                      <BasicTooltip asChild content={data.first_file_found}>
                        <a
                          href={data.first_file_found}
                          rel="noreferrer"
                          target="_blank"
                        >
                          <img
                            alt=""
                            className={styles.firstFileFound}
                            src={data.first_file_found}
                          />
                        </a>
                      </BasicTooltip>
                    </InputContent>
                  ) : (
                    <InputValue label="First file found" />
                  )}
                  <InputValue
                    label="Files checked"
                    value={data?.files_checked}
                  />
                </>
              ) : null}
            </FormRow>
          </Wizard.Content>
        </Wizard.Item>
      </Wizard.Root>
    </div>
  )
}
