import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Taxon } from 'data-services/models/taxa'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Input, InputContent } from 'design-system/components/input/input'
import { TaxonInfo } from 'design-system/components/taxon/taxon-info/taxon-info'
import { useState } from 'react'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { TaxonSearch } from '../taxon-search/taxon-search'
import styles from './suggest-id.module.scss'

export const SuggestId = ({ occurrenceId }: { occurrenceId: string }) => {
  const [open, setOpen] = useState(false)

  if (!open) {
    return <Button label="Suggest ID" onClick={() => setOpen(true)} />
  }

  return (
    <SuggestIdForm
      occurrenceId={occurrenceId}
      onCancel={() => setOpen(false)}
    />
  )
}

const SuggestIdForm = ({
  occurrenceId,
  onCancel,
}: {
  occurrenceId: string
  onCancel: () => void
}) => {
  const [taxon, setTaxon] = useState<Taxon>()
  const { createIdentification, isLoading, error } = useCreateIdentification(
    () => onCancel()
  )
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <div className={styles.wrapper}>
      {formError ? (
        <div className={styles.formError}>
          <span>{formError}</span>
        </div>
      ) : null}
      <div className={styles.content}>
        <span className={styles.new}>New ID</span>
        <InputContent label="Taxon">
          {taxon && (
            <div className={styles.taxon}>
              <TaxonInfo taxon={taxon} />
            </div>
          )}
          <div className={styles.taxonActions}>
            <TaxonSearch onChange={setTaxon} />
          </div>
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
              createIdentification({
                occurrenceId: occurrenceId,
                taxonId: taxon?.id,
              })
            }}
          />
        </div>
      </div>
    </div>
  )
}
