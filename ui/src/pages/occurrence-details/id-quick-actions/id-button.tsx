import { IdentificationFieldValues } from 'data-services/hooks/identifications/types'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { useMemo } from 'react'
import styles from './id-quick-actions.module.scss'
import { useRecentIdentifications } from './useRecentOptions'

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

  const { createIdentifications, isLoading, isSuccess, error } =
    useCreateIdentifications(occurrenceIds)
  const { addRecentIdentification } = useRecentIdentifications()

  return (
    <BasicTooltip asChild>
      <Button
        customClass={styles.idButton}
        details={details}
        disabled={isSuccess}
        icon={
          isSuccess ? IconType.RadixCheck : error ? IconType.Error : undefined
        }
        label={label}
        loading={isLoading}
        theme={error ? ButtonTheme.Error : undefined}
        onClick={() => {
          addRecentIdentification({ label, details, value: taxonId })
          createIdentifications(identificationParams)
        }}
      />
    </BasicTooltip>
  )
}
