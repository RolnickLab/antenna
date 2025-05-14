import { FormError } from 'components/form/layout/layout'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { TaxonRanks } from 'components/taxon/taxon-ranks/taxon-ranks'
import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Taxon } from 'data-services/models/taxa'
import { InputContent } from 'design-system/components/input/input'
import { Loader2Icon } from 'lucide-react'
import { Box, Button, Input } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { useRecentIdentifications } from '../reject-id/useRecentOptions'
import { StatusLabel } from '../status-label/status-label'

interface SuggestIdProps {
  occurrenceId: string
  onCancel: () => void
}

export const SuggestId = ({ occurrenceId, onCancel }: SuggestIdProps) => {
  const { projectId } = useParams()
  const [taxon, setTaxon] = useState<Taxon>()
  const [comment, setComment] = useState('')
  const { createIdentification, isLoading, error } =
    useCreateIdentification(onCancel)
  const { addRecentIdentification } = useRecentIdentifications()
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <Box className="p-0 relative">
      {formError && (
        <FormError message={formError} style={{ padding: '8px 16px' }} />
      )}
      <div className="grid gap-4 px-4 py-6">
        <StatusLabel label={translate(STRING.NEW_ID)} />
        <InputContent label={translate(STRING.FIELD_LABEL_TAXON)}>
          <TaxonSelect
            triggerLabel={taxon ? taxon.name : 'Select a value'}
            taxon={taxon}
            onTaxonChange={setTaxon}
          />
          {taxon && (
            <TaxonRanks
              ranks={taxon.ranks}
              getLink={(id: string) =>
                getAppRoute({
                  to: APP_ROUTES.TAXON_DETAILS({
                    projectId: projectId as string,
                    taxonId: id,
                  }),
                })
              }
            />
          )}
        </InputContent>
        <InputContent label={translate(STRING.FIELD_LABEL_COMMENT)}>
          <Input
            name="comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </InputContent>
        <div className="grid grid-cols-2 gap-4">
          <Button onClick={onCancel} size="small" variant="outline">
            <span> {translate(STRING.CANCEL)}</span>
          </Button>
          <Button
            disabled={!taxon}
            size="small"
            onClick={() => {
              if (!taxon) {
                return
              }
              addRecentIdentification({
                label: taxon.name,
                details: taxon.rank,
                value: taxon.id,
              })
              createIdentification({
                occurrenceId: occurrenceId,
                taxonId: taxon.id,
                comment: comment,
              })
            }}
          >
            <span>{translate(STRING.SUBMIT)}</span>
            {isLoading ? <Loader2Icon className="w-4 h-4 ml-2" /> : null}
          </Button>
        </div>
      </div>
    </Box>
  )
}
