import styles from './overview.module.scss'
import { Plot } from 'design-system/components/plot/plot'

const data = {
  y: [18, 45, 98, 120, 109, 113, 43],
  x: ['8PM', '9PM', '10PM', '11PM', '12PM', '13PM', '14PM'],
  tickvals: ['8PM', '', '', '', '', '', '14PM'],
}

export const Overview = () => {
  return (
    <>
      <div className={styles.section}>
        <span className={styles.title}>Graph examples</span>
        <div className={styles.plots}>
          <div className={styles.plotWrapper}>
            <Plot title="19 Jun" data={data} />
          </div>
          <div className={styles.plotWrapper}>
            <Plot title="20 Jun" data={data} type="scatter" />
          </div>
          <div className={styles.plotWrapper}>
            <Plot
              title="21 Jun"
              data={data}
              type="scatter"
              showRangeSlider={true}
            />
          </div>
        </div>
      </div>
    </>
  )
}
