import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import * as Popover from 'design-system/components/popover/popover'
import { RefObject, useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { REJECT_OPTIONS } from './constants'
import { RejectIdButton } from './reject-id-button'
import styles from './reject-id.module.scss'

interface RejectIdProps {
  occurrenceId: string
  occurrenceTaxonId: string
  containerRef?: RefObject<HTMLDivElement>
}

export const RejectId = ({
  occurrenceId,
  occurrenceTaxonId,
  containerRef,
}: RejectIdProps) => {
  const [open, setIsOpen] = useState(false)

  useEffect(() => {
    // Close popover after taxon update
    setIsOpen(false)
  }, [occurrenceTaxonId])

  return (
    <Popover.Root open={open} onOpenChange={setIsOpen}>
      <Popover.Trigger>
        <Button
          label={translate(STRING.REJECT_ID_SHORT)}
          icon={IconType.ToggleDown}
          customClass={styles.triggerButton}
        />
      </Popover.Trigger>
      <Popover.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        align="start"
        side="right"
        container={containerRef?.current ?? undefined}
      >
        <div className={styles.wrapper}>
          <span className={styles.description}>
            {translate(STRING.REJECT_ID)}
          </span>
          <div className={styles.settings}>
            {REJECT_OPTIONS.map((option) => (
              <RejectIdButton
                key={option.value}
                occurrenceId={occurrenceId}
                applied={occurrenceTaxonId === option.value}
                label={option.label}
                value={option.value}
              />
            ))}
          </div>
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
