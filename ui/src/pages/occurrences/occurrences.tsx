import { Card } from 'design-system/components/card/card'
import * as Tabs from 'design-system/components/tabs/tabs'
import React from 'react'
import styles from './occurrences.module.scss'

const createMockMoth = (id: string, height = 400) => {
  return {
    id,
    title: 'Lorem ipsum',
    subTitle: 'Lorem ipsum dolor sit amet',
    image: {
      src: `https://placekitten.com/600/400`,
      alt: '',
    },
  }
}

const mockMoths = [
  createMockMoth('moth-01'),
  createMockMoth('moth-02'),
  createMockMoth('moth-03'),
  createMockMoth('moth-04'),
  createMockMoth('moth-05'),
  createMockMoth('moth-06'),
  createMockMoth('moth-07'),
  createMockMoth('moth-08'),
]

export const Occurrences = () => {
  return (
    <div className={styles.wrapper}>
      <Tabs.Root defaultValue="table">
        <Tabs.List>
          <Tabs.Trigger value="table" label="Table" />
          <Tabs.Trigger value="gallery" label="Gallery" />
        </Tabs.List>
        <Tabs.Content value="table">
          <div className={styles.content}></div>
        </Tabs.Content>
        <Tabs.Content value="gallery">
          <div className={styles.content}>
            <div className={styles.sidebar}></div>
            <div className={styles.gallery}>
              {mockMoths.map((moth) => (
                <Card
                  key={moth.id}
                  title={moth.title}
                  subTitle={moth.subTitle}
                  image={moth.image}
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
