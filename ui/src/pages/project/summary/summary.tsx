import { useStatus } from 'data-services/hooks/useStatus'
import { ProjectDetails } from 'data-services/models/project-details'
import { Box } from 'design-system/components/box/box'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'
import { UploadImagesDialog } from 'pages/captures/upload-images-dialog/upload-images-dialog'
import { useOutletContext } from 'react-router-dom'
import { UserPermission } from 'utils/user/types'
import { DeploymentsMap } from './deployments-map'

export const Summary = () => {
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()
  const { status } = useStatus(project.id)
  const canUpload = project.userPermissions.includes(UserPermission.Update)

  return (
    <div className="grid gap-6">
      {status && status.numCaptures === 0 && canUpload ? (
        <div className="flex flex-col items-center pt-32">
          <h1 className="mb-8 heading-large">Welcome!</h1>
          <p className="text-center body-large mb-16">
            To fill your project with data, upload a few sample images or
            configure a data source.
          </p>
          <UploadImagesDialog buttonSize="default" buttonVariant="success" />
        </div>
      ) : (
        <>
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
        </>
      )}
    </div>
  )
}
