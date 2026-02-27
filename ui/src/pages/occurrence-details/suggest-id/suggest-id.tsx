import { FormError } from 'components/form/layout/layout'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { Taxon } from 'data-services/models/taxa'
import { Loader2Icon } from 'lucide-react'
import { Button, Input } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { useRecentIdentifications } from '../id-quick-actions/useRecentOptions'

interface SuggestIdProps {
  occurrenceIds: string[]
  onCancel: () => void
}

export const SuggestId = ({ occurrenceIds, onCancel }: SuggestIdProps) => {
  const [taxon, setTaxon] = useState<Taxon>()
  const [comment, setComment] = useState('')
  const { createIdentifications, isLoading, error } = useCreateIdentifications(
    occurrenceIds,
    onCancel
  )
  const { addRecentIdentification } = useRecentIdentifications()
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <>
      {formError && (
        <FormError message={formError} style={{ padding: '8px 16px' }} />
      )}
      <div className="px-4 py-6">
        <div className="mb-8">
          <span className="block body-overline-small font-semibold text-muted-foreground mb-2">
            {translate(STRING.FIELD_LABEL_TAXON)}
          </span>
          <TaxonSelect
            triggerLabel={
              taxon ? taxon.name : translate(STRING.SELECT_TAXON_PLACEHOLDER)
            }
            taxon={taxon}
            onTaxonChange={setTaxon}
          />
        </div>
        <div className="mb-8">
          <span className="block body-overline-small font-semibold text-muted-foreground mb-2">
            {translate(STRING.FIELD_LABEL_COMMENT)}
          </span>
          <Input
            name="comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button onClick={onCancel} size="small" variant="outline">
            <span> {translate(STRING.CANCEL)}</span>
          </Button>
          <Button
            disabled={!taxon}
            size="small"
            variant="success"
            onClick={() => {
              if (!taxon) {
                return
              }
              addRecentIdentification({
                label: taxon.name,
                details: taxon.rank,
                value: taxon.id,
              })
              createIdentifications(
                occurrenceIds.map((occurrenceId) => ({
                  occurrenceId,
                  taxonId: taxon.id,
                  comment: comment,
                }))
              )
            }}
          >
            <span>{translate(STRING.SAVE)}</span>
            {isLoading ? <Loader2Icon className="w-4 h-4 ml-2" /> : null}
          </Button>
        </div>
      </div>
    </>
  )
}
