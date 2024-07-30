import { usePopulateCollection } from 'data-services/hooks/collections/usePopulateCollection'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'

export const PopulateCollection = ({
  collectionId,
}: {
  collectionId: string
}) => {
  const { populateCollection, isLoading, isSuccess } = usePopulateCollection()

  if (isSuccess) {
    return (
      <Button
        label={translate(STRING.QUEUED)}
        icon={IconType.RadixClock}
        theme={ButtonTheme.Neutral}
        disabled={true}
      />
    )
  }

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
      label={translate(STRING.POPULATE)}
      loading={isLoading}
      theme={ButtonTheme.Success}
      onClick={() => populateCollection(collectionId)}
    />
  )
}
