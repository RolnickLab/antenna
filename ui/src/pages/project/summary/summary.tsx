import { useStatus } from 'data-services/hooks/useStatus'
import { ProjectDetails } from 'data-services/models/project-details'
import { Box } from 'design-system/components/box/box'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'
import * as Tabs from 'design-system/components/tabs/tabs'
import { UploadImagesDialog } from 'pages/captures/upload-images-dialog/upload-images-dialog'
import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { UserPermission } from 'utils/user/types'
import { DeploymentsMap } from './deployments-map'

export const Summary = () => {
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()
  const [isOpen, setIsOpen] = useState(false)
  const { status } = useStatus(project.id)
  const canUpload = project.userPermissions.includes(UserPermission.Update)
  const showUpload = status && status.numCaptures === 0 && canUpload

  return (
    <div className="grid gap-6">
      {showUpload || isOpen ? (
        <div className="flex flex-col items-center pt-32">
          <h1 className="mb-8 heading-large">Welcome!</h1>
          <p className="text-center body-large mb-16">
            To fill your project with data, upload a few sample images or
            configure a data source.
          </p>
          <UploadImagesDialog
            buttonSize="default"
            buttonVariant="success"
            isOpen={isOpen}
            setIsOpen={setIsOpen}
          />
        </div>
      ) : (
        <>
          <DeploymentsMap deployments={project.deployments} />
          <Tabs.Root defaultValue={project.summaryData[0]?.id}>
            <Tabs.List>
              {project.summaryData.map((section) => (
                <Tabs.Trigger
                  key={section.id}
                  label={section.title}
                  value={section.id}
                />
              ))}
            </Tabs.List>
            {project.summaryData.map((section) => (
              <Tabs.Content key={section.id} value={section.id}>
                <PlotGrid>
                  {section.plots.map((plot, index) => (
                    <Box key={index}>
                      <Plot
                        data={plot.data}
                        orientation={plot.orientation}
                        title={plot.title}
                        type={plot.type}
                      />
                    </Box>
                  ))}
                </PlotGrid>
              </Tabs.Content>
            ))}
          </Tabs.Root>
        </>
      )}
    </div>
  )
}
