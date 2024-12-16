import { FormRow } from 'components/form/layout/layout'
import { useTestBackendConnection } from 'data-services/hooks/backends/useTestBackendConnection'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import * as Wizard from 'design-system/components/wizard/wizard'
import { useEffect, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { StatusInfo } from './status-info/status-info'
import { Status } from './status-info/types'
import styles from './backends.module.scss'

export const ConnectionStatus = ({
  regex,
  showDetails,
  backendId,
  subdir,
  updatedAt,
  onConnectionChange,
}: {
  regex?: string
  showDetails?: boolean
  backendId: string
  subdir?: string
  updatedAt?: string
  onConnectionChange?: (isConnected: boolean) => void
}) => {
  const { data, testBackendConnection, isLoading, error, validationError } =
    useTestBackendConnection()
  const [lastUpdated, setLastUpdated] = useState<Date>()

  const update = async () => {
    await testBackendConnection({ id: backendId, subdir, regex })
    setLastUpdated(new Date())
  }

  const status = (() => {
    if (data?.server_live) {
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
    if (data?.server_live) {
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
  }, [backendId, subdir, regex, updatedAt])

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
            <StatusInfo label={label} status={status} tooltip={details} />
          </Wizard.Trigger>
          <Wizard.Content className={styles.wizardContent}>
            <FormRow>
              <InputValue label="Server Status" value={data?.server_live ? 'Online' : 'Offline'} />
              <InputValue label="Pipelines Online" value={data?.pipelines_online.length} />
            </FormRow>
          </Wizard.Content>
        </Wizard.Item>
      </Wizard.Root>
    </div>
  )
}
