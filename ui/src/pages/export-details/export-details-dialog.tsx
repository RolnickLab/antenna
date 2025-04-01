import classNames from 'classnames'
import { FormRow, FormSection } from 'components/form/layout/layout'
import { useExportDetails } from 'data-services/hooks/exports/useExportDetails'
import { Export } from 'data-services/models/export'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputContent, InputValue } from 'design-system/components/input/input'
import inputStyles from 'design-system/components/input/input.module.scss'
import { StatusBar } from 'design-system/components/status/status-bar'
import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import _ from 'lodash'
import { DownloadIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const ExportDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { exportDetails, isLoading, error } = useExportDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.EXPORTS({
              projectId: projectId as string,
            }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
      >
        <Dialog.Header
          title={translate(STRING.ENTITY_DETAILS, {
            type: _.capitalize(translate(STRING.ENTITY_TYPE_EXPORT)),
          })}
        />
        <div className={styles.content}>
          {exportDetails ? (
            <ExportDetailsContent exportDetails={exportDetails} />
          ) : null}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const ExportDetailsContent = ({ exportDetails }: { exportDetails: Export }) => {
  const { projectId } = useParams()

  return (
    <>
      <FormSection title={translate(STRING.SUMMARY)}>
        <FormRow>
          <InputValue
            label={translate(STRING.FIELD_LABEL_TYPE)}
            value={exportDetails.type.label}
          />
          <InputValue
            label="Filters"
            value={exportDetails.filtersLabels.join('\n')}
          />
        </FormRow>
        <FormRow>
          <InputValue
            label={translate(STRING.FIELD_LABEL_CREATED_AT)}
            value={exportDetails.createdAt}
          />
          <InputValue
            label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
            value={exportDetails.updatedAt}
          />
        </FormRow>
        <FormRow>
          <InputContent label={translate(STRING.FIELD_LABEL_JOB_STATUS)}>
            <div className="flex items-center gap-2">
              <StatusMarker color={exportDetails.job.status.color} />
              <span className={classNames(inputStyles.value, 'pt-0.5')}>
                {exportDetails.job.status.label}
              </span>
            </div>
          </InputContent>
          <InputValue
            label={translate(STRING.FIELD_LABEL_JOB)}
            value={exportDetails.job.name}
            to={APP_ROUTES.JOB_DETAILS({
              projectId: projectId as string,
              jobId: exportDetails.job.id,
            })}
          />
        </FormRow>
        <FormRow>
          <InputValue
            label={translate(STRING.FIELD_LABEL_RECORDS_EXPORTED)}
            value={exportDetails.numRecords}
          />
          <InputValue
            label={translate(STRING.FIELD_LABEL_SIZE)}
            value={
              exportDetails.fileSizeLabel?.length
                ? exportDetails.fileSizeLabel
                : undefined
            }
          />
        </FormRow>
      </FormSection>
      <FormSection title={translate(STRING.FIELD_LABEL_RESULT)}>
        <div>
          {exportDetails.job.progress.value !== 1 ? (
            <StatusBar
              color={exportDetails.job.status.color}
              progress={exportDetails.job.progress.value}
            />
          ) : (
            <a
              href={exportDetails.fileUrl}
              download={exportDetails.fileUrl}
              className={classNames(
                buttonVariants({
                  variant: 'outline',
                }),
                '!w-auto !rounded-full'
              )}
            >
              <DownloadIcon className="w-4 h-4" />
              <span>{translate(STRING.DOWNLOAD)}</span>
            </a>
          )}
        </div>
      </FormSection>
    </>
  )
}
