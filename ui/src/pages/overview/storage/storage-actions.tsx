import { useSyncStorage } from 'data-services/hooks/storage-sources/useSyncStorage'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'

export const SyncStorage = ({ storageId: storageId }: { storageId: string }) => {
    const { syncStorage, isLoading, isSuccess } = useSyncStorage()

    if (isSuccess) {
        return (
            <Button
                label={translate(STRING.QUEUED)}
                icon={IconType.RadixClock}
                theme={ButtonTheme.Neutral}
            />
        )
    }

    return (
        <Button
            label={translate(STRING.SYNC)}
            loading={isLoading}
            theme={ButtonTheme.Success}
            onClick={() => syncStorage(storageId)}
        />
    )
}
