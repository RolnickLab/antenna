import { FormRow, FormSection } from 'components/form/layout/layout'
import { API_ROUTES } from 'data-services/constants'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { CaptureDetails } from 'data-services/models/capture-details'
import { ChevronDownIcon } from 'lucide-react'
import {
  Button,
  EntityPicker,
  InputContent,
  Popover,
  StatusMarker,
} from 'nova-ui-kit'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { ProcessNow } from './process-now'

export const Process = ({ capture }: { capture?: CaptureDetails }) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const [pipelineId, setPipelineId] = useState(
    project?.settings.defaultProcessingPipeline?.id
  )

  if (!capture) {
    return (
      <Button disabled size="small" variant="outline">
        <span>{translate(STRING.PROCESS)}</span>
        <ChevronDownIcon className="w-4 h-4" />
      </Button>
    )
  }

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button size="small" variant="outline">
          {capture.currentJob &&
          capture.currentJob.status.code !== 'SUCCESS' ? (
            <StatusMarker color={capture.currentJob.status.color} />
          ) : null}
          <span>{translate(STRING.PROCESS)}</span>
          <ChevronDownIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content className="p-0 w-96" align="end">
        <FormSection
          title={translate(STRING.PROCESS)}
          description={
            capture.userPermissions.includes(UserPermission.RunSingleImage)
              ? translate(STRING.MESSAGE_PROCESS_NOW_TOOLTIP)
              : translate(STRING.MESSAGE_PERMISSIONS_MISSING)
          }
        >
          <div className="flex flex-col items-end gap-4">
            <EntityPicker
              collection={API_ROUTES.PIPELINES}
              onValueChange={setPipelineId}
              value={pipelineId}
            />
            <ProcessNow capture={capture} pipelineId={pipelineId} />
          </div>
        </FormSection>
        {capture.currentJob ?? capture.numJobs ? (
          <FormSection>
            <FormRow>
              {capture.currentJob ? (
                <InputContent
                  label={translate(STRING.FIELD_LABEL_LATEST_JOB_STATUS)}
                >
                  <div className="flex items-center gap-2">
                    <StatusMarker color={capture.currentJob.status.color} />
                    <span className="pt-0.5 body-base">
                      {capture.currentJob.status.label}
                    </span>
                  </div>
                </InputContent>
              ) : null}
              <InputContent label={translate(STRING.FIELD_LABEL_JOBS)}>
                <Link
                  className="bubble-label"
                  to={getAppRoute({
                    to: APP_ROUTES.JOBS({
                      projectId: projectId as string,
                    }),
                    filters: {
                      source_image_single: capture.id,
                    },
                  })}
                >
                  <span>{capture.numJobs}</span>
                </Link>
              </InputContent>
            </FormRow>
          </FormSection>
        ) : null}
      </Popover.Content>
    </Popover.Root>
  )
}
