import { Taxon } from 'data-services/models/taxa'
import * as Popover from 'design-system/components/popover/popover'
import { EllipsisVerticalIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { RefObject, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { REJECT_OPTIONS } from './constants'
import { IdButton } from './id-button'
import styles from './id-quick-actions.module.scss'
import { useRecentIdentifications } from './useRecentOptions'
import { getCommonRanks } from './utils'

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
  const { recentIdentifications } = useRecentIdentifications()

  const sections: {
    title: string
    options: { label: string; details?: string; value: string }[]
    subSections?: {
      title: string
      options: { label: string; details?: string; value: string }[]
    }[]
  }[] = [
    {
      title: translate(STRING.APPLY_ID),
      options: getCommonRanks(occurrenceTaxons).map(({ id, name, rank }) => ({
        label: name,
        details: rank,
        value: id,
      })),
      subSections: recentIdentifications.length
        ? [
            {
              title: translate(STRING.RECENT),
              options: recentIdentifications,
            },
          ]
        : undefined,
    },
    {
      title: translate(STRING.REJECT_ID),
      options: REJECT_OPTIONS,
    },
  ]

  return (
    <Popover.Root open={open} onOpenChange={setIsOpen}>
      <Popover.Trigger asChild>
        <Button
          className="w-8 h-8 text-primary-600"
          size="icon"
          variant="outline"
        >
          <EllipsisVerticalIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        align="start"
        side="right"
        container={containerRef?.current ?? undefined}
        disableOutsideClose
        style={{ zIndex }}
      >
        <div className={styles.wrapper}>
          {sections.map((section, index) => (
            <div key={index} className={styles.section}>
              <span className={styles.title}>{section.title}</span>
              <div className={styles.options}>
                {section.options.length ? (
                  section.options.map((option) => (
                    <IdButton
                      key={option.value}
                      occurrenceIds={occurrenceIds}
                      label={option.label}
                      taxonId={option.value}
                      details={option.details}
                    />
                  ))
                ) : (
                  <span className={styles.info}>No options available.</span>
                )}
                {section.subSections?.map((subSection, index) => (
                  <div key={index} className={styles.subSection}>
                    <span className={styles.subTitle}>{subSection.title}</span>
                    <div className={styles.options}>
                      {subSection.options.map((option) => (
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
                ))}
              </div>
            </div>
          ))}
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
