import { FormError, FormSection } from 'components/form/layout/layout'
import { useSyncAllDeployments } from 'data-services/hooks/deployments/useSyncAllDeployments'
import { CheckIcon, EyeIcon, Loader2Icon, RefreshCwIcon } from 'lucide-react'
import { BasicTooltip, Button, buttonVariants, Dialog } from 'nova-ui-kit'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

export const SyncAllDeploymentsDialog = ({
  projectId,
  count,
}: {
  projectId: string
  count: number
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const { syncAllDeployments, reset, isLoading, isSuccess, error, data } =
    useSyncAllDeployments()

  const queued = data?.data.queued
  const errorMessage = error ? parseServerError(error)?.message : undefined

  return (
    <Dialog.Root
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        // The hook stays mounted with the header, so reset on open to offer a
        // fresh sync instead of the previous run's result. Skip the reset while a
        // request is in flight: reset() clears the loading state without
        // cancelling the request, so resetting here would re-enable Sync all and
        // allow a duplicate bulk run.
        if (open && !isLoading) {
          reset()
        }
      }}
    >
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <RefreshCwIcon className="w-4 h-4" />
          <span>{translate(STRING.SYNC_ALL)}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        {errorMessage && <FormError message={errorMessage} />}
        <FormSection
          title={translate(STRING.SYNC_ALL)}
          description={translate(STRING.MESSAGE_SYNC_ALL_CONFIRM, { count })}
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
                // The error is surfaced via FormError; swallow the rejection so a
                // failed request does not log an unhandled promise rejection.
                void syncAllDeployments(projectId).catch(() => undefined)
              }}
              size="small"
              variant="success"
            >
              <span>{translate(STRING.SYNC_ALL)}</span>
              {isSuccess ? (
                <CheckIcon className="w-4 h-4" />
              ) : isLoading ? (
                <Loader2Icon className="w-4 h-4 animate-spin" />
              ) : null}
            </Button>
            {isSuccess && queued !== undefined && (
              <BasicTooltip asChild content={translate(STRING.VIEW_JOBS)}>
                <Link
                  aria-label={translate(STRING.VIEW_JOBS)}
                  className={buttonVariants({ size: 'icon', variant: 'ghost' })}
                  to={getAppRoute({
                    to: APP_ROUTES.JOBS({ projectId }),
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
