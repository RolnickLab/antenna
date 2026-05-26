import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { FormError, FormSection } from '../layout/layout'

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
      {errorMessage && <FormError message={errorMessage} />}
      <FormSection
        title={translate(STRING.ENTITY_DELETE, { type })}
        description={translate(STRING.MESSAGE_DELETE_CONFIRM, { type })}
      >
        <div className="flex justify-end gap-4">
          <Button onClick={onCancel} size="small" variant="outline">
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <Button
            disabled={isLoading || isSuccess}
            onClick={onSubmit}
            size="small"
            variant="destructive"
          >
            <span>
              {isSuccess ? translate(STRING.DELETED) : translate(STRING.DELETE)}
            </span>
            {isSuccess ? (
              <CheckIcon className="w-4 h-4" />
            ) : isLoading ? (
              <Loader2Icon className="w-4 h-4 animate-spin" />
            ) : null}
          </Button>
        </div>
      </FormSection>
    </>
  )
}
