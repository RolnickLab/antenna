import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Taxon } from 'data-services/models/taxa'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Input, InputContent } from 'design-system/components/input/input'
import { useState } from 'react'
import { useParams } from 'react-router'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { StatusLabel } from '../status-label/status-label'
import { TaxonSearch } from '../taxon-search/taxon-search'
import styles from './suggest-id.module.scss'

interface SuggestIdProps {
  occurrenceId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const SuggestId = ({
  occurrenceId,
  open,
  onOpenChange,
}: SuggestIdProps) => {
  if (!open) {
    return null
  }

  return (
    <SuggestIdForm
      occurrenceId={occurrenceId}
      onCancel={() => onOpenChange(false)}
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
  const { projectId } = useParams()
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
        <StatusLabel label="New ID" />
        <InputContent label="Taxon">
          {taxon && (
            <div className={styles.taxon}>
              <TaxonInfo
                taxon={taxon}
                getLink={(id: string) =>
                  getAppRoute({
                    to: APP_ROUTES.SPECIES_DETAILS({
                      projectId: projectId as string,
                      speciesId: id,
                    }),
                  })
                }
              />
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
