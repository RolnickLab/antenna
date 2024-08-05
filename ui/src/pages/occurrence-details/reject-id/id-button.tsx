import { IdentificationFieldValues } from 'data-services/hooks/identifications/types'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
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
    useCreateIdentifications(identificationParams)
  const { addRecentIdentification } = useRecentIdentifications()

  return (
    <Tooltip content={error} contentStyle={{ zIndex: 3 }}>
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
          createIdentifications()
        }}
      />
    </Tooltip>
  )
}
