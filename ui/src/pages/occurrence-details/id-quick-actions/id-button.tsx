import classNames from 'classnames'
import { IdentificationFieldValues } from 'data-services/hooks/identifications/types'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { IconType } from 'design-system/components/icon/icon'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useMemo } from 'react'
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
    <BasicTooltip asChild content={error}>
      <Button
        className={classNames('justify-between', { 'text-destructive': error })}
        details={details}
        disabled={isSuccess}
        icon={
          isSuccess ? IconType.RadixCheck : error ? IconType.Error : undefined
        }
        onClick={() => {
          addRecentIdentification({ label, details, value: taxonId })
          createIdentifications(identificationParams)
        }}
        size="small"
        variant="outline"
      >
        <span>{label}</span>
        {error ? (
          <AlertCircleIcon className="w-4 h-4" />
        ) : isSuccess ? (
          <CheckIcon className="w-4 h-4" />
        ) : isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : (
          <span className="body-overline-xsmall text-muted-foreground">
            {details}
          </span>
        )}
      </Button>
    </BasicTooltip>
  )
}
