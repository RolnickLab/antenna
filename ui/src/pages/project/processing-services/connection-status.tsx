import { FormRow } from 'components/form/layout/layout'
import { useTestProcessingServiceConnection } from 'data-services/hooks/processing-services/useTestProcessingServiceConnection'
import { InputValue } from 'design-system/components/input/input'
import * as Wizard from 'design-system/components/wizard/wizard'
import { useEffect, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import styles from './processing-services.module.scss'
import { StatusInfo } from './status-info/status-info'
import { Status } from './status-info/types'

export const ConnectionStatus = ({
  regex,
  processingServiceId,
  subdir,
  updatedAt,
  onConnectionChange,
}: {
  regex?: string
  processingServiceId: string
  subdir?: string
  updatedAt?: string
  onConnectionChange?: (isConnected: boolean) => void
}) => {
  const {
    data,
    testProcessingServiceConnection: testProcessingServiceConnection,
    isLoading,
    error,
    validationError,
  } = useTestProcessingServiceConnection()
  const [lastUpdated, setLastUpdated] = useState<Date>()

  const update = async () => {
    try {
      await testProcessingServiceConnection({
        id: processingServiceId,
        subdir,
        regex,
      })
    } catch {
      // Error handled in hook
    }

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
  }, [processingServiceId, subdir, regex, updatedAt])

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
              <InputValue
                label="Server Status"
                value={data?.server_live ? 'Online' : 'Offline'}
              />
              <InputValue
                label="Pipelines available"
                value={data?.pipelines_online.length}
              />
            </FormRow>
          </Wizard.Content>
        </Wizard.Item>
      </Wizard.Root>
    </div>
  )
}
