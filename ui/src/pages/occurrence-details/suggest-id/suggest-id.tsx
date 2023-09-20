import { Taxon } from 'data-services/models/taxa'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Input } from 'design-system/components/input/input'
import * as Popover from 'design-system/components/popover/popover'
import { TaxonInfo } from 'design-system/components/taxon/taxon-info/taxon-info'
import { useEffect, useState } from 'react'
import { TaxonSearch } from '../taxon-search/taxon-search'
import styles from './suggest-id.module.scss'

export const SuggestId = ({ containerId }: { containerId?: string }) => {
  const [open, setOpen] = useState(false)
  const [taxon, setTaxon] = useState<Taxon>()
  const container = containerId ? document.getElementById(containerId) : null

  useEffect(() => {
    setTaxon(undefined)
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
        <div className={styles.content}>
          <div>
            <div className={styles.taxon}>
              <TaxonInfo taxon={taxon} />
            </div>
            <div className={styles.taxonActions}>
              <TaxonSearch onChange={setTaxon} />
            </div>
          </div>
          <Input name="comment" label="Comment" />
          <div className={styles.formActions}>
            <Button label="Cancel" onClick={() => setOpen(false)} />
            <Button label="Submit" theme={ButtonTheme.Success} />
          </div>
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
