import { useFeatureOccurrence } from 'data-services/hooks/occurrences/useFeatureOccurrence'
import { useUnfeatureOccurrence } from 'data-services/hooks/occurrences/useUnfeatureOccurrence'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { Loader2Icon, StarIcon } from 'lucide-react'
import { Button, CONSTANTS } from 'nova-ui-kit'
import { useState } from 'react'

interface FeatureControlProps {
  occurrenceId: string
}

export const FeatureControl = ({ occurrenceId }: FeatureControlProps) => {
  const [featured, setFeatured] =
    useState(false) /* TODO: Use backend status here when avaible */
  const { featureOccurrence, isLoading: featureIsLoading } =
    useFeatureOccurrence(occurrenceId, () => setFeatured(true))
  const { unfeatureOccurrence, isLoading: unfeatureIsLoading } =
    useUnfeatureOccurrence(occurrenceId, () => setFeatured(false))

  return (
    <BasicTooltip
      content={featured ? 'Unfeature occurrence' : 'Feature occurrence'}
    >
      <Button
        onClick={() => {
          if (featured) {
            unfeatureOccurrence()
          } else {
            featureOccurrence()
          }
        }}
        size="icon"
        variant="outline"
      >
        {featureIsLoading || unfeatureIsLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : (
          <StarIcon
            className="w-4 h-4"
            fill={featured ? CONSTANTS.COLORS.primary[600] : 'transparent'}
          />
        )}
      </Button>
    </BasicTooltip>
  )
}
