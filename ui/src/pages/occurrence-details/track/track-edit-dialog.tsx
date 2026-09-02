import { FormError, FormMessage } from 'components/form/layout/layout'
import { Loader2Icon } from 'lucide-react'
import { Button, Dialog } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

/**
 * Confirmation step shared by the track edits. Passing `result` replaces the
 * confirm button with what happened, so an edit never completes silently.
 */
export const TrackEditDialog = ({
  children,
  confirmDisabled,
  confirmLabel,
  description,
  error,
  isLoading,
  onConfirm,
  onOpenChange,
  open,
  result,
  title,
}: {
  children?: ReactNode
  confirmDisabled?: boolean
  confirmLabel: string
  description: string
  error?: unknown
  isLoading?: boolean
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
  open: boolean
  result?: string
  title: string
}) => {
  const errorMessage = error ? parseServerError(error).message : undefined

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <Dialog.Header title={title} />
        <div className="flex flex-col gap-4 p-6">
          <span className="body-small text-muted-foreground">
            {description}
          </span>
          {children}
          {errorMessage ? <FormError message={errorMessage} /> : null}
          {result ? <FormMessage message={result} withIcon /> : null}
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
            )}
          </div>
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
