import { Occurrence } from 'data-services/models/occurrence'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Popover from 'design-system/components/popover/popover'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './occurrence-details.module.scss'

const mockData = {
  taxonomy:
    'https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Meropleon_diversicolor_-_Multicolored_Sedgeminer_Moth_%289810621354%29.jpg/440px-Meropleon_diversicolor_-_Multicolored_Sedgeminer_Moth_%289810621354%29.jpg',
  taxonomyDescription:
    'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum sodales cursus porta. Proin nec quam turpis.',
  images: [
    'https://api.dev.insectai.org/static/crops/43ee45ae97381dce5e9147e34f90b1c7.jpg',
    'https://api.dev.insectai.org/static/crops/77d106412b6c81a6257a81e25abe59ea.jpg',
  ],
}

export const OccurrenceDetails = ({
  occurrence,
}: {
  occurrence?: Occurrence
}) => {
  const [showTaxonomy, setShowTaxonomy] = useState(false)

  if (!occurrence) {
    return (
      <div className={styles.content}>
        <div className={styles.info}>
          <Error />
        </div>
      </div>
    )
  }

  const fields = [
    {
      label: translate(STRING.DETAILS_LABEL_DEPLOYMENT),
      value: occurrence.deployment,
    },
    {
      label: translate(STRING.DETAILS_LABEL_SESSION),
      value: occurrence.sessionLabel,
    },
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
          <Popover.Root open={showTaxonomy} onOpenChange={setShowTaxonomy}>
            <Popover.Trigger
              onMouseEnter={() => setShowTaxonomy(true)}
              onMouseLeave={() => setShowTaxonomy(false)}
            >
              <span className={styles.title}>{occurrence.categoryLabel}</span>
            </Popover.Trigger>
            <Popover.Content
              ariaCloselabel={translate(STRING.CLOSE)}
              align="start"
              side="bottom"
              hideClose
            >
              <div className={styles.taxonomyPopover}>
                <img src={mockData.taxonomy} />
                <div className={styles.taxonomyContent}>
                  <p>{mockData.taxonomyDescription}</p>
                </div>
              </div>
            </Popover.Content>
          </Popover.Root>
          <span className={styles.details}>WIP</span>
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
          {occurrence.images.slice(0, 2).map((image, index) => (
            <div
              key={index}
              className={styles.imageWrapper}
              style={{
                backgroundImage: `url(${image.src})`,
              }}
            ></div>
          ))}
        </div>
      </div>
    </div>
  )
}
