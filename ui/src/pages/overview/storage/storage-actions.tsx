import { useSyncStorage } from 'data-services/hooks/storage-sources/useSyncStorage'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { STRING, translate } from 'utils/language'

export const SyncStorage = ({
  storageId: storageId,
}: {
  storageId: string
}) => {
  const { syncStorage, isLoading, isSuccess, error, validationError } =
    useSyncStorage()

  if (isSuccess) {
    return (
      <Button
        label={translate(STRING.CONNECTED)}
        icon={IconType.RadixClock}
        theme={ButtonTheme.Success}
      />
    )
  } else if (error) {
    return (
      <Tooltip
        content={validationError?.detail || translate(STRING.UNKNOWN_ERROR)}
      >
        <Button
          icon={IconType.Error}
          label={translate(STRING.FAILED)}
          theme={ButtonTheme.Error}
          onClick={() => {
            syncStorage(storageId)
          }}
        />
      </Tooltip>
    )
  }

  return (
    <Button
      label={translate(STRING.TEST_CONNECTION)}
      loading={isLoading}
      theme={ButtonTheme.Neutral}
      onClick={() => syncStorage(storageId)}
    />
  )
}
