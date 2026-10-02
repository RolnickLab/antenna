import { DefaultFiltersTooltip } from 'components/filtering/default-filter-control'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { SettingsIcon } from 'lucide-react'
import { BasicTooltip, Button, Checkbox, Popover } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export interface ViewSettingsValues {
  defaultFilters: boolean
  showDetections: boolean
  showPathCrops: boolean
}

export const ViewSettings = ({
  onSettingsChange,
  settings,
  showTrackingSettings,
}: {
  onSettingsChange: (settings: ViewSettingsValues) => void
  settings: ViewSettingsValues
  showTrackingSettings?: boolean
}) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)

  return (
    <Popover.Root>
      <BasicTooltip asChild content={translate(STRING.VIEW_SETTINGS)}>
        <Popover.Trigger asChild>
          <Button
            aria-label={translate(STRING.VIEW_SETTINGS)}
            size="icon"
            variant="ghost"
          >
            <SettingsIcon className="w-4 h-4" />
          </Button>
        </Popover.Trigger>
      </BasicTooltip>
      <Popover.Content className="grid gap-4" align="end" side="bottom">
        <span className="body-base font-semibold text-muted-foreground">
          {translate(STRING.VIEW_SETTINGS)}
        </span>
        <div className="grid gap-2">
          <Checkbox
            id="show-detections"
            label={translate(STRING.SHOW_DETECTIONS)}
            checked={settings.showDetections}
            onCheckedChange={() =>
              onSettingsChange({
                ...settings,
                showDetections: !settings.showDetections,
              })
            }
          />
          {showTrackingSettings ? (
            <Checkbox
              id="show-path-crops"
              label={translate(STRING.SHOW_PATH_CROPS)}
              checked={settings.showPathCrops}
              onCheckedChange={() =>
                onSettingsChange({
                  ...settings,
                  showPathCrops: !settings.showPathCrops,
                })
              }
            />
          ) : null}
          <div className="flex items-center gap-1">
            <Checkbox
              id="default-filters"
              label={translate(STRING.NAV_ITEM_DEFAULT_FILTERS)}
              checked={settings.defaultFilters}
              onCheckedChange={() =>
                onSettingsChange({
                  ...settings,
                  defaultFilters: !settings.defaultFilters,
                })
              }
              disabled // If enabled we should refetch session data based on this setting
            />
            {project ? <DefaultFiltersTooltip project={project} /> : null}
          </div>
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
