import classNames from 'classnames'
import { ErrorState } from 'components/error-state/error-state'
import { useTopIdentifiers } from 'data-services/hooks/occurrences/stats/useTopIdentifiers'
import { useLatestOccurrences } from 'data-services/hooks/occurrences/useLatestOccurrences'
import { useProjectCharts } from 'data-services/hooks/projects/useProjectCharts'
import { useTopSpecies } from 'data-services/hooks/species/useTopSpecies'
import { useStatus } from 'data-services/hooks/useStatus'
import { ProjectDetails } from 'data-services/models/project-details'
import { Box, buttonVariants } from 'design-system'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { PlotGrid } from 'design-system/components/plot-grid/plot-grid'
import { Plot } from 'design-system/components/plot/lazy-plot'
import * as Tabs from 'design-system/components/tabs/tabs'
import { UploadImagesDialog } from 'pages/captures/upload-images-dialog/upload-images-dialog'
import { useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
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
    <div className="grid gap-8 md:gap-12">
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
            <h2 className="mb-4 heading-small">{translate(STRING.OVERVIEW)}</h2>
            <div className="grid gap-8 xl:grid-cols-3">
              <div>
                <h3 className="mb-4 body-large font-medium">
                  {translate(STRING.LATEST_OCCURRENCES)}
                </h3>
                <LatestOccurrences projectId={project.id} />
              </div>
              <div>
                <h3 className="mb-4 body-large font-medium">
                  {translate(STRING.MOST_IDENTIFICATIONS)}
                </h3>
                <MostIdentifications projectId={project.id} />
              </div>
              <div>
                <h3 className="mb-4 body-large font-medium">
                  {translate(STRING.MOST_OBSERVED_TAXA)}
                </h3>
                <MostObservedTaxa projectId={project.id} />
              </div>
            </div>
          </div>
          <div>
            <h2 className="mb-4 heading-small">{translate(STRING.CHARTS)}</h2>
            <Charts projectId={project.id} />
          </div>
        </>
      )}
    </div>
  )
}

const SummaryColumn = ({
  isLoading,
  error,
  isEmpty,
  viewAllHref,
  children,
}: {
  isLoading: boolean
  error: unknown
  isEmpty: boolean
  viewAllHref: string
  children: React.ReactNode
}) => {
  if (isLoading) {
    return <LoadingSpinner />
  }

  if (error) {
    return <ErrorState compact error={error} />
  }

  if (isEmpty) {
    return (
      <p className="body-small text-muted-foreground">
        {translate(STRING.MESSAGE_NO_RESULTS_TO_SHOW)}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-background">{children}</div>
      <Link
        to={viewAllHref}
        className={classNames(
          buttonVariants({ size: 'small', variant: 'outline' }),
          'self-end'
        )}
      >
        <span>{translate(STRING.VIEW_ALL)}</span>
      </Link>
    </div>
  )
}

const LatestOccurrences = ({ projectId }: { projectId: string }) => {
  const { occurrences, isLoading, error } = useLatestOccurrences(projectId)

  return (
    <SummaryColumn
      isLoading={isLoading}
      error={error}
      isEmpty={!occurrences?.length}
      viewAllHref={`${APP_ROUTES.OCCURRENCES({
        projectId,
      })}?ordering=-first_appearance_timestamp`}
    >
      {occurrences?.map((occurrence) => (
        <Link
          key={occurrence.id}
          className="w-full border-border border-b last:border-none"
          to={APP_ROUTES.OCCURRENCE_DETAILS({
            projectId,
            occurrenceId: occurrence.id,
          })}
        >
          <ListItem
            item={{
              image: { src: occurrence.images[0]?.src },
              text: occurrence.dateLabel,
              title: occurrence.determinationTaxon.name,
            }}
          />
        </Link>
      ))}
    </SummaryColumn>
  )
}

const MostIdentifications = ({ projectId }: { projectId: string }) => {
  const { data, isLoading, error } = useTopIdentifiers(projectId)

  return (
    <SummaryColumn
      isLoading={isLoading}
      error={error}
      isEmpty={!data?.top_identifiers.length}
      viewAllHref={`${APP_ROUTES.OCCURRENCES({ projectId })}?verified=true`}
    >
      {data?.top_identifiers.map((user) => (
        <div key={user.id} className="border-border border-b last:border-none">
          <ListItem
            item={{
              image: { src: user.image, variant: 'user' },
              title: user.name?.length
                ? user.name
                : translate(STRING.ANONYMOUS_USER),
            }}
            count={user.identification_count}
          />
        </div>
      ))}
    </SummaryColumn>
  )
}

const MostObservedTaxa = ({ projectId }: { projectId: string }) => {
  const { species, isLoading, error } = useTopSpecies(projectId)

  return (
    <SummaryColumn
      isLoading={isLoading}
      error={error}
      isEmpty={!species?.length}
      viewAllHref={`${APP_ROUTES.TAXA({
        projectId,
      })}?ordering=-occurrences_count`}
    >
      {species?.map((species) => (
        <Link
          key={species.id}
          className="w-full border-border border-b last:border-none"
          to={APP_ROUTES.TAXON_DETAILS({
            projectId,
            taxonId: species.id,
          })}
        >
          <ListItem
            item={{
              image: { src: species.coverImageUrl ?? undefined },
              title: species.name,
            }}
            count={species.numOccurrences}
          />
        </Link>
      ))}
    </SummaryColumn>
  )
}

const Charts = ({ projectId }: { projectId: string }) => {
  const { projectCharts, isLoading, error } = useProjectCharts(projectId)

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (error) {
    return <ErrorState compact error={error} />
  }

  if (!projectCharts?.length) {
    return (
      <p className="body-small text-muted-foreground">
        {translate(STRING.MESSAGE_NO_RESULTS_TO_SHOW)}
      </p>
    )
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
              <Box key={index} className="bg-background">
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
