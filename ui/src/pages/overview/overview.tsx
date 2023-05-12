import styles from './overview.module.scss'
import { Plot } from 'design-system/components/plot/plot'
import {
  MultipleMarkerMap,
  MarkerPosition,
} from 'design-system/map/multiple-marker-map'

const data = {
  y: [18, 45, 98, 120, 109, 113, 43],
  x: ['8PM', '9PM', '10PM', '11PM', '12PM', '13PM', '14PM'],
  tickvals: ['8PM', '', '', '', '', '', '14PM'],
}

const deployments = [
  new MarkerPosition(52.30767, 5.04011),
  new MarkerPosition(52.31767, 5.06011),
  new MarkerPosition(52.32767, 5.09011),
]

export const Overview = () => {
  return (
    <>
      <div className={styles.section}>
        <div className={styles.content}>
          <div className={styles.about}>
            <div>
              <span className={styles.title}>Example title</span>
              <p className={styles.text}>
                Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                Curabitur a sapien quis ligula suscipit tristique ullamcorper
                porta tellus. Sed non quam lectus. Fusce nec elit ac tortor
                viverra interdum quis at augue. Proin at lobortis ligula. Nullam
                sed accumsan ex. Donec a pretium nisl.
              </p>
            </div>
            <MultipleMarkerMap markerPositions={deployments} />
          </div>
        </div>
      </div>
      <div className={styles.section}>
        <div className={styles.content}>
          <span className={styles.label}>Example plots</span>
          <div className={styles.plots}>
            <Plot title="19 Jun" data={data} />
            <Plot title="20 Jun" data={data} type="scatter" />
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
