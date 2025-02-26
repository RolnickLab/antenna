import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { FormError } from '../layout/layout'

export const DeleteForm = ({
  type,
  error,
  isLoading,
  isSuccess,
  onCancel,
  onSubmit,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  type: string
  onCancel: () => void
  onSubmit: () => void
}) => {
  const errorMessage = error ? parseServerError(error)?.message : undefined

  return (
    <>
      {errorMessage ? (
        <FormError message={errorMessage} style={{ padding: '8px 16px' }} />
      ) : null}
      <div className="grid gap-4 px-4 py-6">
        <span className="body-overline-small font-semibold text-muted-foreground">
          {translate(STRING.ENTITY_DELETE, { type })}
        </span>
        <span className="body-small">
          {translate(STRING.MESSAGE_DELETE_CONFIRM, { type })}
        </span>
        <div className="grid grid-cols-2 gap-4">
          <Button onClick={onCancel} size="small" variant="outline">
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <Button
            disabled={isSuccess}
            onClick={onSubmit}
            size="small"
            variant="destructive"
          >
            {isSuccess ? <CheckIcon className="w-4 h-4 mr-2" /> : null}
            <span>
              {isSuccess ? translate(STRING.DELETED) : translate(STRING.DELETE)}
            </span>
            {isLoading ? (
              <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
            ) : null}
          </Button>
        </div>
      </div>
    </>
  )
}
