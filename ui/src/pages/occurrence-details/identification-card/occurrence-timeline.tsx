import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import {
  getFallbackTimelineItems,
  getTimelineItems,
  ServerOccurrenceHistoryEntry,
} from 'data-services/models/occurrence-history'
import { Loader2Icon } from 'lucide-react'
import { useMemo } from 'react'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'
import { AlgorithmResult } from './algorithm-result'
import { HumanIdentification } from './human-identification'
import { MachinePrediction } from './machine-prediction'
import { TrackReview } from './track-review'

export const OccurrenceTimeline = ({
  currentUser,
  entries,
  error,
  isLoading,
  occurrence,
  onConfirmed,
}: {
  currentUser?: UserInfo
  entries?: ServerOccurrenceHistoryEntry[]
  error?: unknown
  isLoading: boolean
  occurrence: Occurrence
  onConfirmed?: (occurrenceId: string) => void
}) => {
  const items = useMemo(
    () =>
      entries
        ? getTimelineItems({
            determinationTaxonId: occurrence.determinationTaxon?.id,
            entries,
            identifications: occurrence.humanIdentifications,
            predictions: occurrence.machinePredictions,
          })
        : getFallbackTimelineItems({
            identifications: occurrence.humanIdentifications,
            predictions: occurrence.machinePredictions,
          }),
    [entries, occurrence]
  )

  return (
    <>
      {isLoading ? (
        <div className="flex justify-center py-2">
          <Loader2Icon className="w-4 h-4 animate-spin text-muted-foreground" />
        </div>
      ) : null}
      {error ? (
        <p className="px-2 body-small text-muted-foreground">
          {translate(STRING.HISTORY_LOAD_ERROR)}
        </p>
      ) : null}
      {!isLoading && !items.length ? (
        <p className="px-2 body-small text-muted-foreground">
          {translate(STRING.HISTORY_EMPTY)}
        </p>
      ) : null}
      {items.map((item) => {
        switch (item.type) {
          case 'identification':
            return (
              <HumanIdentification
                key={item.id}
                currentUser={currentUser}
                identification={item.identification}
                occurrence={occurrence}
                onConfirmed={onConfirmed}
                user={item.identification.user}
              />
            )
          case 'prediction':
            return (
              <MachinePrediction
                key={item.id}
                currentUser={currentUser}
                identification={item.prediction}
                occurrence={occurrence}
                onConfirmed={onConfirmed}
              />
            )
          case 'algorithm_result':
            return (
              <AlgorithmResult
                key={item.id}
                currentUser={currentUser}
                entry={item.entry}
                occurrence={occurrence}
                onConfirmed={onConfirmed}
              />
            )
          case 'review':
            return <TrackReview key={item.id} entry={item.entry} />
        }
      })}
    </>
  )
}
