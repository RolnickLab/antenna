import { IdentificationFieldValues } from 'data-services/hooks/identifications/types'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { useMemo } from 'react'
import styles from './id-quick-actions.module.scss'

interface IdButtonProps {
  details?: string
  label: string
  occurrenceIds: string[]
  taxonId: string
}

export const IdButton = ({
  details,
  label,
  occurrenceIds,
  taxonId,
}: IdButtonProps) => {
  const identificationParams: IdentificationFieldValues[] = useMemo(
    () =>
      occurrenceIds.map((occurrenceId) => ({
        occurrenceId,
        taxonId,
      })),
    [occurrenceIds, taxonId]
  )

  const { createIdentifications, isLoading, isSuccess } =
    useCreateIdentifications(identificationParams)

  return (
    <Button
      label={label}
      details={details}
      icon={isSuccess ? IconType.RadixCheck : undefined}
      loading={isLoading}
      disabled={isSuccess}
      customClass={styles.idButton}
      onClick={() => createIdentifications()}
    />
  )
}
