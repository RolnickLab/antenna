import { ProjectDetails } from 'data-services/models/project-details'
import { Box } from 'design-system/components/box/box'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'
import { useOutletContext } from 'react-router-dom'
import { DeploymentsMap } from './deployments-map'

export const Summary = () => {
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()

  return (
    <div className="grid gap-6">
      <DeploymentsMap deployments={project.deployments} />
      <PlotGrid>
        {project.summaryData.map((summary, index) => (
          <Box key={index}>
            <Plot
              title={summary.title}
              data={summary.data}
              orientation={summary.orientation}
              type={summary.type}
            />
          </Box>
        ))}
      </PlotGrid>
    </div>
  )
}
