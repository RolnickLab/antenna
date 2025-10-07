import {
  FormActions,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { ProjectDetails } from 'data-services/models/project-details'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { InputValue } from 'design-system/components/input/input'
import { ChevronRightIcon } from 'lucide-react'
import { buttonVariants, Popover } from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DefaultFiltersControl = () => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)

  return (
    <div className="flex items-center justify-between pl-2">
      <div className="flex items-center gap-1">
        <span className="text-muted-foreground body-overline-small font-bold pt-0.5">
          {translate(STRING.NAV_ITEM_DEFAULT_FILTERS)}
        </span>
        {project ? <DefaultFiltersPopover project={project} /> : null}
      </div>
    </div>
  )
}

export const DefaultFiltersPopover = ({
  buttonTheme = IconButtonTheme.Plain,
  project,
}: {
  buttonTheme?: IconButtonTheme
  project: ProjectDetails
}) => (
  <Popover.Root>
    <Popover.Trigger asChild>
      <IconButton
        icon={IconType.Info}
        shape={IconButtonShape.Round}
        theme={buttonTheme}
      />
    </Popover.Trigger>
    <Popover.Content className="p-0">
      <FormSection
        title={translate(STRING.NAV_ITEM_DEFAULT_FILTERS)}
        description="Data is filtered by default based on global project configuration."
      >
        <FormRow>
          <InputValue
            label="Score threshold"
            value={project.settings.scoreThreshold}
          />
        </FormRow>
        <FormRow
          style={
            project.featureFlags.default_filters
              ? undefined
              : { display: 'none' }
          }
        >
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
      </FormSection>
      {project.canUpdate ? (
        <FormActions>
          <Link
            className={buttonVariants({ size: 'small', variant: 'outline' })}
            to={APP_ROUTES.DEFAULT_FILTERS({ projectId: project.id })}
          >
            <span>Configure</span>
            <ChevronRightIcon className="w-4 h-4" />
          </Link>
        </FormActions>
      ) : null}
    </Popover.Content>
  </Popover.Root>
)
