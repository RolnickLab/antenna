import { useProject } from 'data-services/hooks/useProjects'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Plot } from 'design-system/components/plot/plot'
import { Error } from 'pages/error/error'
import { DeploymentsMap } from './deployments-map/deployments-map'
import styles from './overview.module.scss'

const EXAMPLE_DATA = {
  y: [18, 45, 98, 120, 109, 113, 43],
  x: ['8PM', '9PM', '10PM', '11PM', '12PM', '13PM', '14PM'],
  tickvals: ['8PM', '', '', '', '', '', '14PM'],
}

export const Overview = () => {
  const { project, isLoading, error } = useProject()

  if (!isLoading && error) {
    return <Error />
  }

  if (isLoading || !project) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <>
      <div className={styles.about}>
        <div className={styles.aboutImage}>
          <img src={project?.image} alt="" />
        </div>
        <div className={styles.aboutInfo}>
          <h1 className={styles.title}>{project.name}</h1>
          <p className={styles.description}>{project.description}</p>
          <DeploymentsMap deployments={project.deployments} />
        </div>
      </div>
      <div className={styles.plotsContainer}>
        <div className={styles.plotsContent}>
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
