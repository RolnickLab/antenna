import { useOccurrences } from 'data-services/useOccurrences'
import { Card } from 'design-system/components/card/card'
import * as Tabs from 'design-system/components/tabs/tabs'
import React from 'react'
import { OccurrencesTable } from './occurrences-table/occurrences-table'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  const occurrences = useOccurrences()

  return (
    <div className={styles.wrapper}>
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
              {occurrences.map((occurrence, index) => (
                <Card
                  key={index}
                  title={occurrence.categoryLabel}
                  subTitle={occurrence.familyLabel}
                  image={{
                    src: 'https://placekitten.com/600/400',
                    alt: '',
                  }}
                  maxWidth="262px"
                />
              ))}
            </div>
          </div>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
