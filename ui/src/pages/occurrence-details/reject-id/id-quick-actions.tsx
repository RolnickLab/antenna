import { Taxon } from 'data-services/models/taxa'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import * as Popover from 'design-system/components/popover/popover'
import { RefObject, useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { REJECT_OPTIONS } from './constants'
import { IdButton } from './id-button'
import styles from './id-quick-actions.module.scss'

interface RejectIdProps {
  occurrenceId: string
  occurrenceTaxon: Taxon
  containerRef?: RefObject<HTMLDivElement>
}

export const IdQuickActions = ({
  occurrenceId,
  occurrenceTaxon,
  containerRef,
}: RejectIdProps) => {
  const [open, setIsOpen] = useState(false)

  const sections = [
    {
      title: translate(STRING.APPLY_ID),
      options: [...occurrenceTaxon.ranks].reverse().map(({ id, rank }) => ({
        label: `${translate(STRING.APPLY_ID_SHORT)} ${rank.toLowerCase()}`,
        value: id,
      })),
    },
    { title: translate(STRING.REJECT_ID), options: REJECT_OPTIONS },
  ]

  useEffect(() => {
    // Close popover after taxon update
    setIsOpen(false)
  }, [occurrenceTaxon.id])

  return (
    <Popover.Root open={open} onOpenChange={setIsOpen}>
      <Popover.Trigger>
        <IconButton icon={IconType.Options} />
      </Popover.Trigger>
      <Popover.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        align="start"
        side="right"
        container={containerRef?.current ?? undefined}
      >
        <div className={styles.wrapper}>
          {sections.map((section, index) => (
            <div key={index} className={styles.section}>
              <span className={styles.title}>{section.title}</span>
              <div className={styles.options}>
                {section.options.map((option) => (
                  <IdButton
                    key={option.value}
                    occurrenceId={occurrenceId}
                    applied={occurrenceTaxon.id === option.value}
                    label={option.label}
                    value={option.value}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
