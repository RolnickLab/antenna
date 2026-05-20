import { Taxon } from 'data-services/models/taxa'
import { Button, Popover } from 'design-system'
import { EllipsisVerticalIcon } from 'lucide-react'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { IdButton } from './id-button'
import styles from './id-quick-actions.module.scss'
import { useRecentIdentifications } from './useRecentOptions'
import { useRejectOptions } from './useRejectOptions'
import { getCommonRanks } from './utils'

interface IdQuickActionsProps {
  occurrenceIds: string[]
  occurrenceTaxa: Taxon[]
}

export const IdQuickActions = ({
  occurrenceIds = [],
  occurrenceTaxa = [],
}: IdQuickActionsProps) => {
  const [open, setIsOpen] = useState(false)
  const { recentIdentifications } = useRecentIdentifications()
  const { rejectOptions } = useRejectOptions()

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
      options: getCommonRanks({
        occurrenceTaxa,
        rejectOptions,
      }).map(({ id, name, rank }) => ({
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
      options: rejectOptions,
    },
  ]

  return (
    <Popover.Root open={open} onOpenChange={setIsOpen}>
      <Popover.Trigger asChild>
        <Button
          aria-label={translate(STRING.MORE)}
          size="icon"
          variant="outline"
        >
          <EllipsisVerticalIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content className="p-0 w-auto" align="end" side="right">
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
