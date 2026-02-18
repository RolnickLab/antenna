import { FormError } from 'components/form/layout/layout'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { SUCCESS_TIMEOUT } from 'data-services/constants'
import { useAddTaxaListTaxon } from 'data-services/hooks/taxa-lists/useAddTaxaListTaxon'
import { Taxon } from 'data-services/models/taxa'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

export const AddTaxaListTaxon = ({
  onCancel,
  taxaListId,
}: {
  onCancel: () => void
  taxaListId: string
}) => {
  const { projectId } = useParams()
  const [taxon, setTaxon] = useState<Taxon>()
  const { addTaxaListTaxon, error, isLoading, isSuccess } = useAddTaxaListTaxon(
    projectId as string
  )
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <>
      {formError && (
        <FormError message={formError} style={{ padding: '8px 16px' }} />
      )}
      <div className="px-4 py-6">
        <div className="mb-4">
          <TaxonSelect
            triggerLabel={taxon ? taxon.name : 'Select a taxon'}
            taxon={taxon}
            onTaxonChange={setTaxon}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button onClick={onCancel} size="small" variant="outline">
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <Button
            disabled={!taxon || isLoading}
            onClick={async () => {
              if (taxon) {
                await addTaxaListTaxon({ taxaListId, taxonId: taxon.id })
                setTimeout(() => setTaxon(undefined), SUCCESS_TIMEOUT)
              }
            }}
            size="small"
            variant="success"
          >
            <span>{translate(STRING.ADD)}</span>
            {isSuccess ? (
              <CheckIcon className="w-4 h-4 ml-2" />
            ) : isLoading ? (
              <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
            ) : null}
          </Button>
        </div>
      </div>
    </>
  )
}
