import { TaxonFilter } from 'components/filtering/filters/taxon-filter'
import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useActiveTaxonId } from './hooks/useActiveTaxon'

// The session's most frequent taxa, offered before the user types a search.
const MAX_SESSION_TAXA = 10

export const CaptureTaxonFilter = ({
  numShown,
  numTotal,
  sessionId,
}: {
  numShown: number
  numTotal: number
  sessionId: string
}) => {
  const { projectId } = useParams()
  const { activeTaxonId, setActiveTaxonId } = useActiveTaxonId()
  const { species: sessionTaxa } = useSpecies({
    projectId,
    filters: [{ field: 'event', value: sessionId }],
    pagination: { page: 0, perPage: MAX_SESSION_TAXA },
    sort: { field: 'occurrences_count', order: 'desc' },
  })

  return (
    <div className="flex items-center gap-1">
      <div className="w-56">
        <TaxonFilter
          defaultTaxa={sessionTaxa}
          placeholder={translate(STRING.FILTER_BY_TAXON)}
          value={activeTaxonId}
          onAdd={setActiveTaxonId}
          onClear={() => setActiveTaxonId(undefined)}
        />
      </div>
      {activeTaxonId ? (
        <>
          <span className="pt-0.5 body-small text-muted-foreground whitespace-nowrap">
            {translate(STRING.RESULTS_DETECTIONS_SHOWN, {
              shown: numShown,
              total: numTotal,
            })}
          </span>
          <Button
            aria-label={translate(STRING.CLEAR)}
            className="shrink-0 text-muted-foreground"
            onClick={() => setActiveTaxonId(undefined)}
            size="icon"
            variant="ghost"
          >
            <XIcon className="w-4 h-4" />
          </Button>
        </>
      ) : null}
    </div>
  )
}
