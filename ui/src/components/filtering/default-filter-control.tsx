import {
  FormActions,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { ProjectDetails } from 'data-services/models/project-details'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { InputValue } from 'design-system/components/input/input'
import { ChevronRightIcon } from 'lucide-react'
import { buttonVariants, Popover } from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'

export const DefaultFiltersControl = () => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)

  return (
    <div className="flex items-center justify-between pl-2">
      <div className="flex items-center gap-1">
        <span className="text-muted-foreground body-overline-small font-bold pt-0.5">
          Default filters
        </span>
        {project ? <InfoPopover project={project} /> : null}
      </div>
      <div className="flex items-center justify-center p-0.5 bg-primary rounded-full">
        <div className="w-4 h-4 rounded-full"></div>
        <div className="w-4 h-4 bg-background rounded-full"></div>
      </div>
    </div>
  )
}

const InfoPopover = ({ project }: { project: ProjectDetails }) => (
  <Popover.Root>
    <Popover.Trigger asChild>
      <IconButton icon={IconType.Info} theme={IconButtonTheme.Plain} />
    </Popover.Trigger>
    <Popover.Content className="p-0">
      <FormSection
        title="Default filters"
        description="Data is filtered by default based on global project configuration."
      >
        <FormRow>
          <InputValue
            label="Score threshold"
            value={project.defaultFilters.scoreThreshold}
          />
        </FormRow>
        <FormRow>
          <InputValue
            label="Include taxa"
            value={project.defaultFilters.includeTaxa
              .map((taxon) => taxon.name)
              .join(', ')}
          />
          <InputValue
            label="Exclude taxa"
            value={project.defaultFilters.excludeTaxa
              .map((taxon) => taxon.name)
              .join(', ')}
          />
        </FormRow>
      </FormSection>
      <FormActions>
        <Link
          className={buttonVariants({ size: 'small', variant: 'outline' })}
          to={APP_ROUTES.DEFAULT_FILTERS({ projectId: project.id })}
        >
          <span>Configure project</span>
          <ChevronRightIcon className="w-4 h-4" />
        </Link>
      </FormActions>
    </Popover.Content>
  </Popover.Root>
)
