import classNames from 'classnames'
import { FormError, FormMessage } from 'components/form/layout/layout'
import { ChevronRightIcon, Loader2Icon } from 'lucide-react'
import { BasicTooltip, Button, buttonVariants, Dialog } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

/** Says why a button is disabled; a disabled button takes no pointer events itself. */
export const DisabledReason = ({
  children,
  reason,
}: {
  children: ReactNode
  reason?: string
}) =>
  reason ? (
    <BasicTooltip asChild content={reason}>
      <span tabIndex={0}>{children}</span>
    </BasicTooltip>
  ) : (
    <>{children}</>
  )

/**
 * Confirmation step shared by the track edits. Passing `result` replaces the
 * confirm button with what happened, so an edit never completes silently.
 */
export const TrackEditDialog = ({
  children,
  confirmDisabled,
  confirmDisabledReason,
  confirmLabel,
  description,
  error,
  isLoading,
  isWide,
  onConfirm,
  onOpenChange,
  open,
  result,
  resultLink,
  title,
}: {
  children?: ReactNode
  confirmDisabled?: boolean
  /** Shown on the confirm button while it is disabled. */
  confirmDisabledReason?: string
  confirmLabel: string
  description: string
  error?: unknown
  isLoading?: boolean
  /** For content that needs more than the compact dialog's width, such as a table. */
  isWide?: boolean
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
  open: boolean
  result?: string
  /** Where the occurrence the edit created can be opened, once there is a result. */
  resultLink?: string
  title: string
}) => {
  // Track edits have no form fields, so a field error from the server is the reason itself.
  const parsedError = error ? parseServerError(error) : undefined
  const errorMessage = parsedError
    ? parsedError.fieldErrors
        .map((fieldError) => fieldError.message)
        .join(' ') || parsedError.message
    : undefined

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isCompact={!isWide}
      >
        <Dialog.Header title={title} />
        <div
          className={classNames('flex flex-col gap-4 p-6', {
            'w-[680px] max-w-full': isWide,
          })}
        >
          <span className="body-small text-muted-foreground">
            {description}
          </span>
          {children}
          {errorMessage ? <FormError message={errorMessage} /> : null}
          {result ? (
            <FormMessage message={result} withIcon>
              {resultLink ? (
                <Link
                  className={buttonVariants({
                    size: 'small',
                    variant: 'ghost',
                  })}
                  to={resultLink}
                >
                  <span>{translate(STRING.TRACK_OPEN_NEW_OCCURRENCE)}</span>
                  <ChevronRightIcon className="w-4 h-4" />
                </Link>
              ) : null}
            </FormMessage>
          ) : null}
          <div className="flex justify-end gap-4">
            <Button
              onClick={() => onOpenChange(false)}
              size="small"
              variant="outline"
            >
              <span>
                {result ? translate(STRING.CLOSE) : translate(STRING.CANCEL)}
              </span>
            </Button>
            {!result && (
              <DisabledReason
                reason={confirmDisabled ? confirmDisabledReason : undefined}
              >
                <Button
                  disabled={confirmDisabled || isLoading}
                  onClick={onConfirm}
                  size="small"
                >
                  <span>{confirmLabel}</span>
                  {isLoading ? (
                    <Loader2Icon className="w-4 h-4 animate-spin" />
                  ) : null}
                </Button>
              </DisabledReason>
            )}
          </div>
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
