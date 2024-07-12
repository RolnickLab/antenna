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
  containerRef?: RefObject<HTMLDivElement>
  occurrenceIds: string[]
  occurrenceTaxons: Taxon[]
  zIndex?: number
}

export const IdQuickActions = ({
  containerRef,
  occurrenceIds = [],
  occurrenceTaxons = [],
  zIndex,
}: RejectIdProps) => {
  const [open, setIsOpen] = useState(false)

  const sections: {
    title: string
    options: { label: string; details?: string; value: string }[]
  }[] = [
    {
      title: translate(STRING.APPLY_ID),
      options: [
        ...occurrenceTaxons.map((occurrenceTaxon) => occurrenceTaxon.ranks),
      ]
        .flat()
        .reverse()
        .filter(
          (obj1, i, arr) => arr.findIndex((obj2) => obj2.id === obj1.id) === i
        )
        .map(({ id, name, rank }) => ({
          label: name,
          details: rank,
          value: id,
        })),
    },
    {
      title: translate(STRING.REJECT_ID),
      options: REJECT_OPTIONS,
    },
  ]

  useEffect(() => {
    // Close popover after taxon update
    setIsOpen(false)
  }, [occurrenceTaxons[0]?.id])

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
        style={{ zIndex }}
      >
        <div className={styles.wrapper}>
          {sections.map((section, index) => {
            if (!section.options.length) {
              return null
            }

            return (
              <div key={index} className={styles.section}>
                <span className={styles.title}>{section.title}</span>
                <div className={styles.options}>
                  {section.options.map((option) => (
                    <IdButton
                      key={option.value}
                      occurrenceIds={occurrenceIds}
                      label={option.label}
                      taxonId={option.value}
                      details={option.details}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
