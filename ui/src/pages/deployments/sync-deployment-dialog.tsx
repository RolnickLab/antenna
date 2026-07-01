import { FormError, FormSection } from 'components/form/layout/layout'
import { useSyncDeploymentSourceImages } from 'data-services/hooks/deployments/useSyncDeploymentSourceImages'
import { CheckIcon, EyeIcon, Loader2Icon, RefreshCwIcon } from 'lucide-react'
import { BasicTooltip, Button, buttonVariants, Dialog } from 'nova-ui-kit'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

export const SyncDeploymentDialog = ({
  id,
  projectId,
}: {
  id: string
  projectId: string
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const {
    syncDeploymentSourceImages,
    reset,
    isLoading,
    isSuccess,
    error,
    data,
  } = useSyncDeploymentSourceImages()

  const jobId = data?.data.job_id
  const errorMessage = error ? parseServerError(error)?.message : undefined

  return (
    <Dialog.Root
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        // The hook is mounted for the whole row, so success/error/data survive
        // a close. Reset on open so reopening offers a fresh sync instead of
        // the previous attempt's stale state.
        if (open) {
          reset()
        }
      }}
    >
      <Dialog.Trigger asChild>
        <Button
          aria-label={translate(STRING.SYNC)}
          className="shrink-0"
          size="icon"
          variant="ghost"
        >
          <RefreshCwIcon className="w-4 h-4" />
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        {errorMessage && <FormError message={errorMessage} />}
        <FormSection
          title={translate(STRING.SYNC_CAPTURES)}
          description={translate(STRING.MESSAGE_SYNC_CONFIRM)}
        >
          <div className="flex items-center justify-end gap-4">
            <Button
              onClick={() => setIsOpen(false)}
              size="small"
              variant="outline"
            >
              <span>{translate(STRING.CANCEL)}</span>
            </Button>
            <Button
              disabled={isLoading || isSuccess}
              onClick={() => {
                // The error is surfaced via `error` state / FormError; swallow
                // the promise rejection so the intended no-data-source 400 does
                // not log an unhandled rejection.
                void syncDeploymentSourceImages(id).catch(() => undefined)
              }}
              size="small"
              variant="success"
            >
              <span>{translate(STRING.SYNC)}</span>
              {isSuccess ? (
                <CheckIcon className="w-4 h-4" />
              ) : isLoading ? (
                <Loader2Icon className="w-4 h-4 animate-spin" />
              ) : null}
            </Button>
            {isSuccess && jobId !== undefined && (
              <BasicTooltip asChild content={translate(STRING.VIEW_JOB)}>
                <Link
                  aria-label={translate(STRING.VIEW_JOB)}
                  className={buttonVariants({ size: 'icon', variant: 'ghost' })}
                  to={getAppRoute({
                    to: APP_ROUTES.JOB_DETAILS({
                      projectId,
                      jobId: String(jobId),
                    }),
                    keepSearchParams: true,
                  })}
                >
                  <EyeIcon className="w-4 h-4" />
                </Link>
              </BasicTooltip>
            )}
          </div>
        </FormSection>
      </Dialog.Content>
    </Dialog.Root>
  )
}
