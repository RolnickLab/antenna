import { Plot } from 'design-system/components/plot/plot'
import { DeploymentsMap } from './deployments-map/deployments-map'
import styles from './overview.module.scss'

const EXAMPLE_DATA = {
  y: [18, 45, 98, 120, 109, 113, 43],
  x: ['8PM', '9PM', '10PM', '11PM', '12PM', '13PM', '14PM'],
  tickvals: ['8PM', '', '', '', '', '', '14PM'],
}

export const Overview = () => (
  <>
    <div className={styles.section}>
      <div className={styles.content}>
        <div className={styles.about}>
          <div className={styles.aboutImage}>
            <p className={styles.text}>Area for project images</p>
          </div>
          <div className={styles.aboutInfo}>
            <h1 className={styles.title}>Example title</h1>
            <p className={styles.text}>
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur
              a sapien quis ligula suscipit tristique ullamcorper porta tellus.
              Sed non quam lectus.
            </p>
            <DeploymentsMap />
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
