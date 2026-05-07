import classNames from 'classnames'
import { ErrorState } from 'components/error-state/error-state'
import { useTopIdentifiers } from 'data-services/hooks/identifications/useTopIdentifiers'
import { useProjectCharts } from 'data-services/hooks/projects/useProjectCharts'
import { useTopSpecies } from 'data-services/hooks/species/useTopSpecies'
import { useStatus } from 'data-services/hooks/useStatus'
import { ProjectDetails } from 'data-services/models/project-details'
import { Box } from 'design-system/components/box/box'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'
import * as Tabs from 'design-system/components/tabs/tabs'
import { buttonVariants } from 'nova-ui-kit'
import { UploadImagesDialog } from 'pages/captures/upload-images-dialog/upload-images-dialog'
import { useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { UserPermission } from 'utils/user/types'
import { DeploymentsMap } from './deployments-map'
import { ListItem } from './list-item'

export const Summary = () => {
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()
  const [isOpen, setIsOpen] = useState(false)
  const { status } = useStatus(project.id)
  const canUpload = project.userPermissions.includes(UserPermission.Update)
  const showUpload = status && status.numCaptures === 0 && canUpload

  return (
    <div className="grid gap-12">
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
          <div>
            <h2 className="mb-4 heading-small">Overview</h2>
            <div className="grid grid-cols-3 gap-8">
              <div>
                <h3 className="mb-4 body-large font-medium">
                  Most identifications
                </h3>
                <MostIdentifications projectId={project.id} />
              </div>
              <div>
                <h3 className="mb-4 body-large font-medium">
                  Most observed taxa
                </h3>
                <MostObservedTaxa projectId={project.id} />
              </div>
            </div>
          </div>
          <div>
            <h2 className="mb-4 heading-small">Charts</h2>
            <Charts projectId={project.id} />
          </div>
        </>
      )}
    </div>
  )
}

const MostIdentifications = ({ projectId }: { projectId: string }) => {
  const { data } = useTopIdentifiers(projectId)

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-background">
        {data?.top_identifiers?.map((user) => (
          <ListItem
            key={user.id}
            item={{
              image: { src: user.image, variant: 'user' },
              text: user.email,
              title: user.name,
            }}
            count={user.identification_count}
          />
        ))}
      </div>
      <Link
        to={`${APP_ROUTES.OCCURRENCES({ projectId })}?verified=-true`}
        className={classNames(
          buttonVariants({ size: 'small', variant: 'success' }),
          'self-end'
        )}
      >
        <span>View all</span>
      </Link>
    </div>
  )
}

const MostObservedTaxa = ({ projectId }: { projectId: string }) => {
  const { species } = useTopSpecies(projectId)

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-background">
        {species?.map((species) => (
          <ListItem
            key={species.id}
            item={{
              image: { src: species.coverImageUrl ?? undefined },

              text: species.name,
            }}
            count={species.numOccurrences}
          />
        ))}
      </div>
      <Link
        to={`${APP_ROUTES.TAXA({ projectId })}?ordering=-occurrences_count`}
        className={classNames(
          buttonVariants({ size: 'small', variant: 'success' }),
          'self-end'
        )}
      >
        <span>View all</span>
      </Link>
    </div>
  )
}

const Charts = ({ projectId }: { projectId: string }) => {
  const { projectCharts, isLoading, error } = useProjectCharts(projectId)

  if (isLoading) {
    return (
      <div className="min-h-[320px] flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  if (error) {
    return <ErrorState error={error} />
  }

  if (!projectCharts?.length) {
    return null
  }

  return (
    <Tabs.Root defaultValue={projectCharts[0].id}>
      <Tabs.List>
        {projectCharts.map((section) => (
          <Tabs.Trigger
            key={section.id}
            label={section.title}
            value={section.id}
          />
        ))}
      </Tabs.List>
      {projectCharts.map((section) => (
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
  )
}
