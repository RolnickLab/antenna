import { FormError } from 'components/form/layout/layout'
import { useCreateOccurrenceSet } from 'data-services/hooks/occurrence-sets/useCreateOccurrenceSet'
import { Loader2Icon } from 'lucide-react'
import { Button, Input } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

interface CreateOccurrenceSetProps {
  occurrenceIds: string[]
  onCancel: () => void
}

export const CreateOccurrenceSet = ({
  occurrenceIds,
  onCancel,
}: CreateOccurrenceSetProps) => {
  const { projectId } = useParams()
  const [name, setName] = useState('')
  const { createOccurrenceSet, isLoading, error } =
    useCreateOccurrenceSet(onCancel)
  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <>
      {formError && (
        <FormError message={formError} style={{ padding: '8px 16px' }} />
      )}
      <div className="px-4 py-6">
        <div className="mb-8">
          <Input
            label={translate(STRING.FIELD_LABEL_NAME)}
            name="name"
            onChange={(e) => setName(e.target.value)}
            value={name}
          />
        </div>
        <span className="block mb-8 body-small text-muted-foreground">
          {translate(STRING.MESSAGE_OCCURRENCE_SET_IS_FIXED, {
            count: `${occurrenceIds.length}`,
          })}
        </span>
        <div className="grid grid-cols-2 gap-2">
          <Button onClick={onCancel} size="small" variant="outline">
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
          <Button
            disabled={!name.length || isLoading}
            onClick={() => {
              if (!projectId) {
                return
              }
              createOccurrenceSet({
                name,
                projectId,
                occurrenceIds,
              })
            }}
            size="small"
            variant="success"
          >
            <span>{translate(STRING.SAVE)}</span>
            {isLoading && <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />}
          </Button>
        </div>
      </div>
    </>
  )
}
