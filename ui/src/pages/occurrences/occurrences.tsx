import { Card } from 'design-system/components/card/card'
import * as Tabs from 'design-system/components/tabs/tabs'
import React from 'react'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  return (
    <div className={styles.wrapper}>
      <Tabs.Root defaultValue="table">
        <Tabs.List>
          <Tabs.Trigger value="table" label="Table" />
          <Tabs.Trigger value="gallery" label="Gallery" />
        </Tabs.List>
        <Tabs.Content value="table">
          <div className={styles.occurrencesContent}></div>
        </Tabs.Content>
        <Tabs.Content value="gallery">
          <div className={styles.galleryContent}>
            <div className={styles.sidebar}></div>
            <div className={styles.gallery}>
              {['a', 'b', 'c', 'd', 'e', 'f'].map((_, index) => (
                <Card
                  key={index}
                  title="Lorem ipsum"
                  subTitle="Lorem ipsum dolor sit amet"
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
