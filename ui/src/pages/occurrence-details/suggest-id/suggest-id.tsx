import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Taxon } from 'data-services/models/taxa'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Input } from 'design-system/components/input/input'
import * as Popover from 'design-system/components/popover/popover'
import { TaxonInfo } from 'design-system/components/taxon/taxon-info/taxon-info'
import { useEffect, useState } from 'react'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { TaxonSearch } from '../taxon-search/taxon-search'
import styles from './suggest-id.module.scss'

export const SuggestId = ({
  occurrenceId,
  containerId,
}: {
  containerId?: string
  occurrenceId: string
}) => {
  const [open, setOpen] = useState(false)
  const [taxon, setTaxon] = useState<Taxon>()
  const { createIdentification, isLoading, error } = useCreateIdentification(
    () => setOpen(false)
  )
  const serverError = error ? parseServerError(error)?.message : undefined
  const container = containerId ? document.getElementById(containerId) : null

  useEffect(() => {
    if (!open) {
      setTaxon(undefined)
    }
  }, [open])

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger>
        <Button label="Suggest ID" />
      </Popover.Trigger>
      <Popover.Content
        ariaCloselabel="Close"
        container={container ?? undefined}
        align="start"
        side="right"
      >
        {serverError ? (
          <div className={styles.formError}>
            <span>{serverError}</span>
          </div>
        ) : null}
        <div className={styles.content}>
          <div>
            <div className={styles.taxon}>
              <TaxonInfo taxon={taxon} />
            </div>
            <div className={styles.taxonActions}>
              <TaxonSearch onChange={setTaxon} />
            </div>
          </div>
          <Input
            disabled
            label="Comment"
            name="comment"
            placeholder="Upcoming feature"
          />

          <div className={styles.formActions}>
            <Button label="Cancel" onClick={() => setOpen(false)} />
            <Button
              label="Submit"
              theme={ButtonTheme.Success}
              loading={isLoading}
              onClick={() => {
                if (taxon) {
                  createIdentification({
                    occurrenceId: occurrenceId,
                    taxonId: taxon?.id,
                  })
                }
              }}
            />
          </div>
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
