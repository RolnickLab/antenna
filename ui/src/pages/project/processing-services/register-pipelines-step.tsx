import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { usePopulateProcessingService } from 'data-services/hooks/processing-services/usePopulateProcessingService'
import {
  ServerRegisterPipelinesResponse,
  ServerTaxaListSyncResult,
} from 'data-services/models/processing-service'
import { Button, Dialog, LoadingSpinner } from 'nova-ui-kit'
import { useEffect } from 'react'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

// Shown right after a processing service is created, instead of just closing the create
// dialog: registration is what makes the service's pipelines, algorithms and taxa lists
// exist in Antenna, and users otherwise never discover they still need to trigger it.
export const RegisterPipelinesStep = ({
  onDone,
  processingServiceId,
  projectId,
}: {
  onDone: () => void
  processingServiceId: string
  projectId?: string
}) => {
  const { populateProcessingService, result, isLoading, error } =
    usePopulateProcessingService(projectId)

  useEffect(() => {
    populateProcessingService(processingServiceId).catch(() => {
      // Error is surfaced below via the hook's error state.
    })
  }, [processingServiceId])

  const errorMessage = error
    ? parseServerError(error).message
    : result && !result.success
    ? result.error ?? translate(STRING.UNKNOWN_ERROR)
    : undefined

  return (
    <>
      <Dialog.Header title={translate(STRING.REGISTER_PIPELINES)} />
      <FormSection>
        {isLoading ? (
          <div className="flex flex-col items-center gap-4 py-8">
            <LoadingSpinner size={32} />
            <span className="body-small text-muted-foreground text-center">
              {translate(STRING.MESSAGE_REGISTERING_PIPELINES)}
            </span>
          </div>
        ) : null}
        {errorMessage ? (
          <FormError
            inDialog
            intro={translate(STRING.MESSAGE_COULD_NOT_REGISTER_PIPELINES)}
            message={errorMessage}
          />
        ) : null}
        {result && result.success ? (
          <RegistrationSummary result={result} />
        ) : null}
      </FormSection>
      <FormActions>
        {errorMessage ? (
          <>
            <Button onClick={onDone} size="small" variant="outline">
              {translate(STRING.CLOSE)}
            </Button>
            <Button
              disabled={isLoading}
              onClick={() => populateProcessingService(processingServiceId)}
              size="small"
              variant="success"
            >
              {translate(STRING.RETRY)}
            </Button>
          </>
        ) : (
          <Button
            disabled={isLoading}
            onClick={onDone}
            size="small"
            variant="success"
          >
            {translate(STRING.DONE)}
          </Button>
        )}
      </FormActions>
    </>
  )
}

const RegistrationSummary = ({
  result,
}: {
  result: ServerRegisterPipelinesResponse
}) => (
  <div className="flex flex-col gap-6">
    <div className="flex flex-col gap-1">
      <p className="body-small">
        {result.pipelines_created.length > 0
          ? translate(STRING.MESSAGE_PIPELINES_REGISTERED, {
              count: result.pipelines_created.length,
            })
          : translate(STRING.MESSAGE_NO_NEW_PIPELINES)}
      </p>
      <p className="body-small">
        {result.algorithms_created.length > 0
          ? translate(STRING.MESSAGE_ALGORITHMS_REGISTERED, {
              count: result.algorithms_created.length,
            })
          : translate(STRING.MESSAGE_NO_NEW_ALGORITHMS)}
      </p>
    </div>
    {result.taxa_lists.length > 0 ? (
      <div className="flex flex-col gap-2">
        <h3 className="body-base font-semibold">
          {translate(STRING.NAV_ITEM_TAXA_LISTS)}
        </h3>
        <ul className="flex flex-col gap-2">
          {result.taxa_lists.map((taxaList) => (
            <li key={taxaList.algorithm_key} className="body-small">
              <TaxaListSummaryLine taxaList={taxaList} />
            </li>
          ))}
        </ul>
      </div>
    ) : null}
  </div>
)

const TaxaListSummaryLine = ({
  taxaList,
}: {
  taxaList: ServerTaxaListSyncResult
}) => {
  if (taxaList.status === 'failed') {
    return (
      <span className="text-destructive">
        {taxaList.algorithm_name}: {taxaList.error}
      </span>
    )
  }

  if (taxaList.status === 'queued') {
    return (
      <span>
        {taxaList.algorithm_name}: {translate(STRING.MESSAGE_TAXA_LIST_QUEUED)}
      </span>
    )
  }

  return (
    <span>
      {taxaList.algorithm_name} — {taxaList.taxa_list_name}:{' '}
      {translate(STRING.MESSAGE_TAXA_LIST_SYNCED, {
        matched: taxaList.matched,
        labels: taxaList.labels,
      })}
      {taxaList.unresolved > 0
        ? ` ${translate(STRING.MESSAGE_TAXA_LIST_UNRESOLVED, {
            count: taxaList.unresolved,
          })}`
        : ''}
    </span>
  )
}
