import { useOccurrences } from 'data-services/useOccurrences'
import { Card } from 'design-system/components/card/card'
import * as Tabs from 'design-system/components/tabs/tabs'
import React from 'react'
import { OccurrencesTable } from './occurrences-table/occurrences-table'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  const occurrences = useOccurrences()

  return (
    <Tabs.Root defaultValue="table">
      <Tabs.List>
        <Tabs.Trigger value="table" label="Table" />
        <Tabs.Trigger value="gallery" label="Gallery" />
      </Tabs.List>
      <Tabs.Content value="table">
        <div className={styles.occurrencesContent}>
          <OccurrencesTable />
        </div>
      </Tabs.Content>
      <Tabs.Content value="gallery">
        <div className={styles.galleryContent}>
          <div className={styles.sidebar}></div>
          <div className={styles.gallery}>
            {occurrences.map((occurrence) => (
              <Card
                key={occurrence.id}
                title={occurrence.categoryLabel}
                subTitle={occurrence.familyLabel}
                image={occurrence.images[0]}
                maxWidth="262px"
              />
            ))}
          </div>
        </div>
      </Tabs.Content>
    </Tabs.Root>
  )
}
