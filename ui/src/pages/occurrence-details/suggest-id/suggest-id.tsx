import { FormError } from 'components/form/layout/layout'
import { TaxonRanks } from 'components/taxon/taxon-ranks/taxon-ranks'
import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Taxon } from 'data-services/models/taxa'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Input, InputContent } from 'design-system/components/input/input'
import { RefObject, useState } from 'react'
import { useParams } from 'react-router'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { StatusLabel } from '../status-label/status-label'
import { TaxonSearch } from '../taxon-search/taxon-search'
import styles from './suggest-id.module.scss'

interface SuggestIdProps {
  inputRef: RefObject<HTMLInputElement>
  occurrenceId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const SuggestId = ({
  inputRef,
  occurrenceId,
  open,
  onOpenChange,
}: SuggestIdProps) => {
  if (!open) {
    return null
  }

  return (
    <SuggestIdForm
      inputRef={inputRef}
      occurrenceId={occurrenceId}
      onCancel={() => onOpenChange(false)}
    />
  )
}

const SuggestIdForm = ({
  inputRef,
  occurrenceId,
  onCancel,
}: {
  inputRef: RefObject<HTMLInputElement>
  occurrenceId: string
  onCancel: () => void
}) => {
  const { projectId } = useParams()
  const [taxon, setTaxon] = useState<Taxon>()
  const { createIdentification, isLoading, error } = useCreateIdentification(
    () => onCancel()
  )
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <div className={styles.wrapper}>
      {formError && (
        <FormError message={formError} style={{ padding: '8px 16px' }} />
      )}
      <div className={styles.content}>
        <StatusLabel label="New ID" />
        <InputContent label="Taxon">
          <div className={styles.taxonActions}>
            <TaxonSearch
              inputRef={inputRef}
              taxon={taxon}
              onTaxonChange={setTaxon}
            />
          </div>
          {taxon && (
            <TaxonRanks
              ranks={taxon.ranks}
              getLink={(id: string) =>
                getAppRoute({
                  to: APP_ROUTES.SPECIES_DETAILS({
                    projectId: projectId as string,
                    speciesId: id,
                  }),
                })
              }
            />
          )}
        </InputContent>
        <Input label="Comment" name="comment" disabled />
        <div className={styles.formActions}>
          <Button label="Cancel" onClick={onCancel} />
          <Button
            label="Submit"
            theme={ButtonTheme.Success}
            loading={isLoading}
            disabled={!taxon}
            onClick={() => {
              if (!taxon) {
                return
              }
              createIdentification({
                occurrenceId: occurrenceId,
                taxonId: taxon.id,
              })
            }}
          />
        </div>
      </div>
    </div>
  )
}
