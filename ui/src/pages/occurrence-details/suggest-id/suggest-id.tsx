import { FormError } from 'components/form/layout/layout'
import { TaxonRanks } from 'components/taxon/taxon-ranks/taxon-ranks'
import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Taxon } from 'data-services/models/taxa'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Input, InputContent } from 'design-system/components/input/input'
import { RefObject, useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { useRecentIdentifications } from '../reject-id/useRecentOptions'
import { StatusLabel } from '../status-label/status-label'
import { TaxonSearch } from '../taxon-search/taxon-search'
import styles from './suggest-id.module.scss'

interface SuggestIdProps {
  containerRef: RefObject<HTMLDivElement>
  inputRef: RefObject<HTMLInputElement>
  occurrenceId: string
  onCancel: () => void
}

export const SuggestId = ({
  containerRef,
  inputRef,
  occurrenceId,
  onCancel,
}: SuggestIdProps) => {
  const { projectId } = useParams()
  const [taxon, setTaxon] = useState<Taxon>()
  const [comment, setComment] = useState('')
  const { createIdentification, isLoading, error } =
    useCreateIdentification(onCancel)
  const { addRecentIdentification } = useRecentIdentifications()
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <div className={styles.wrapper}>
      {formError && (
        <FormError message={formError} style={{ padding: '8px 16px' }} />
      )}
      <div className={styles.content}>
        <StatusLabel label={translate(STRING.NEW_ID)} />
        <InputContent label={translate(STRING.FIELD_LABEL_TAXON)}>
          <div className={styles.taxonActions}>
            <TaxonSearch
              containerRef={containerRef}
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
                  to: APP_ROUTES.TAXON_DETAILS({
                    projectId: projectId as string,
                    taxonId: id,
                  }),
                })
              }
            />
          )}
        </InputContent>
        <Input
          label={translate(STRING.FIELD_LABEL_COMMENT)}
          name="comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        <div className={styles.formActions}>
          <Button label={translate(STRING.CANCEL)} onClick={onCancel} />
          <Button
            label={translate(STRING.SUBMIT)}
            theme={ButtonTheme.Success}
            loading={isLoading}
            disabled={!taxon}
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
          />
        </div>
      </div>
    </div>
  )
}
