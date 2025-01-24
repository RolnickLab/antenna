import { Project } from 'data-services/models/project'
import { Box } from 'design-system/components/box/box'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'

export const Summary = ({ project }: { project: Project }) => (
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
)
