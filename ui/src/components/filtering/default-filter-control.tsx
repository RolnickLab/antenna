import classNames from 'classnames'
import { FormRow } from 'components/form/layout/layout'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { ProjectDetails } from 'data-services/models/project-details'
import { InputValue } from 'design-system/components/input/input'
import { ChevronRightIcon, InfoIcon } from 'lucide-react'
import { Button, buttonVariants, Popover, Switch } from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { booleanToString, stringToBoolean } from './utils'

export const DefaultFiltersControl = ({ field }: { field: string }) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const { filters, addFilter, clearFilter } = useFilters()
  const filter = filters.find((filter) => filter.field === field)

  if (!filter) {
    return null
  }

  return (
    <div className="flex items-center justify-between pl-2">
      <div className="flex items-center gap-1">
        <span className="text-muted-foreground body-overline-small font-bold pt-0.5">
          {filter.label}
        </span>
        {project ? <DefaultFiltersTooltip project={project} /> : null}
      </div>
      <Switch
        checked={stringToBoolean(filter.value) ?? true}
        onCheckedChange={(value) => {
          if (value) {
            clearFilter(field)
          } else {
            addFilter(field, booleanToString(false))
          }
        }}
      />
    </div>
  )
}

export const DefaultFiltersTooltip = ({
  className,
  project,
}: {
  className?: string
  project: ProjectDetails
}) => (
  <Popover.Root>
    <Popover.Trigger asChild>
      <Button
        aria-label={translate(STRING.INFO)}
        className={className}
        size="icon"
        variant="ghost"
      >
        <InfoIcon className="w-4 h-4" />
      </Button>
    </Popover.Trigger>
    <Popover.Content className="p-4 max-w-xs">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-4 border-b border-border pb-4">
          <p className="body-small italic text-muted-foreground">
            {translate(STRING.MESSAGE_DEFAULT_FILTERS)}
          </p>
          <FormRow>
            <InputValue
              label="Score threshold"
              value={project.settings.scoreThreshold}
            />
          </FormRow>
          <FormRow>
            <InputValue
              label="Include taxa"
              value={project.settings.includeTaxa
                .map((taxon) => taxon.name)
                .join(', ')}
            />
            <InputValue
              label="Exclude taxa"
              value={project.settings.excludeTaxa
                .map((taxon) => taxon.name)
                .join(', ')}
            />
          </FormRow>
        </div>
        {project.canUpdate ? (
          <Link
            className={classNames(
              buttonVariants({ size: 'small', variant: 'ghost' }),
              '!w-auto self-end'
            )}
            to={APP_ROUTES.DEFAULT_FILTERS({ projectId: project.id })}
          >
            <span>{translate(STRING.CONFIGURE)}</span>
            <ChevronRightIcon className="w-4 h-4" />
          </Link>
        ) : null}
      </div>
    </Popover.Content>
  </Popover.Root>
)
