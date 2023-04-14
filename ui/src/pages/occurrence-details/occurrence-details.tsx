import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { STRING, translate } from 'utils/language'
import styles from './occurrence-details.module.scss'

const mockData = {
  label: 'Meropleon diversicolor',
  family: 'WIP',
  images: [
    'https://api.dev.insectai.org/static/crops/43ee45ae97381dce5e9147e34f90b1c7.jpg',
    'https://api.dev.insectai.org/static/crops/77d106412b6c81a6257a81e25abe59ea.jpg',
  ],
}

export const OccurrenceDetails = () => {
  const fields = [
    { label: translate(STRING.DETAILS_LABEL_DEPLOYMENT), value: 'WIP' },
    { label: translate(STRING.DETAILS_LABEL_SESSION), value: 'WIP' },
    { label: translate(STRING.DETAILS_LABEL_APPEARANCE), value: 'WIP' },
    { label: translate(STRING.DETAILS_LABEL_ELEVATION), value: 'WIP' },
    { label: translate(STRING.DETAILS_LABEL_AVG_TEMP), value: 'WIP' },
    { label: translate(STRING.DETAILS_LABEL_AVG_WEATHER), value: 'WIP' },
  ]

  const classifications = [
    { label: 'PanamaLeps', value: 'WIP' },
    { label: 'WorldwideLeps', value: 'WIP' },
  ]

  return (
    <div className={styles.content}>
      <div className={styles.column}>
        <div className={styles.header}>
          <span className={styles.title}>{mockData.label}</span>
          <span className={styles.details}>{mockData.family}</span>
        </div>
        <div className={styles.info}>
          <Tabs.Root defaultValue="fields">
            <Tabs.List>
              <Tabs.Trigger
                value="fields"
                label={translate(STRING.TAB_ITEM_FIELDS)}
              />
              <Tabs.Trigger
                value="classification"
                label={translate(STRING.TAB_ITEM_CLASSIFICATION)}
              />
            </Tabs.List>
            <Tabs.Content value="fields">
              <div className={styles.fields}>
                <InfoBlock fields={fields} />
              </div>
            </Tabs.Content>
            <Tabs.Content value="classification">
              <div className={styles.fields}>
                <InfoBlock fields={classifications} />
              </div>
            </Tabs.Content>
          </Tabs.Root>
        </div>
      </div>
      <div className={styles.column}>
        <div className={styles.images}>
          {mockData.images.map((src, index) => (
            <div
              key={index}
              className={styles.imageWrapper}
              style={{
                backgroundImage: `url(${src})`,
              }}
            ></div>
          ))}
        </div>
      </div>
    </div>
  )
}
