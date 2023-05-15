import { Plot } from 'design-system/components/plot/plot'
import { MultipleMarkerMap } from 'design-system/map/multiple-marker-map'
import { EXAMPLE_DATA, EXAMPLE_MARKERS } from './example-data'
import styles from './overview.module.scss'

export const Overview = () => {
  return (
    <>
      <div className={styles.section}>
        <div className={styles.content}>
          <div className={styles.about}>
            <div className={styles.aboutImage}>
              <p className={styles.text}>Area for project images</p>
            </div>
            <div className={styles.aboutInfo}>
              <span className={styles.title}>Example title</span>
              <p className={styles.text}>
                Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                Curabitur a sapien quis ligula suscipit tristique ullamcorper
                porta tellus. Sed non quam lectus.
              </p>
              <MultipleMarkerMap markers={EXAMPLE_MARKERS} />
            </div>
          </div>
        </div>
      </div>
      <div className={styles.section}>
        <div className={styles.content}>
          <span className={styles.label}>Example plots</span>
          <div className={styles.plots}>
            <Plot title="19 Jun" data={EXAMPLE_DATA} />
            <Plot title="20 Jun" data={EXAMPLE_DATA} type="scatter" />
            <Plot
              title="21 Jun"
              data={EXAMPLE_DATA}
              type="scatter"
              showRangeSlider={true}
            />
          </div>
        </div>
      </div>
    </>
  )
}
