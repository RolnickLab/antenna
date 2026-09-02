import { FormMessage } from 'components/form/layout/layout'
import { API_ROUTES } from 'data-services/constants'
import { useCaptureSetDetails } from 'data-services/hooks/capture-sets/useCaptureSetDetails'
import { useEntities } from 'data-services/hooks/entities/useEntities'
import { ChevronRight, XIcon } from 'lucide-react'
import { Button, Select } from 'nova-ui-kit'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

// TODO: Move to src/components, this is not a design system component
export const CaptureSetPicker = ({
  clearable,
  value: _value,
  onValueChange,
}: {
  clearable?: boolean
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { entities = [], isLoading } = useEntities(
    API_ROUTES.CAPTURE_SET_CHOICES,
    { projectId: projectId as string }
  )
  // The choices carry no counts, so the selected set is loaded on its own to report the
  // number of captures it holds.
  const { captureSet, isLoading: isLoadingCaptureSet } = useCaptureSetDetails(
    _value,
    projectId
  )

  // A set picked before it dropped off the end of the list is added back, so an existing
  // selection never silently disappears. One still missing once both fetches have settled
  // no longer exists, and is cleared rather than submitted while the field looks empty.
  const choices = entities.some((entity) => entity.id === _value)
    ? entities
    : [...(captureSet ? [captureSet] : []), ...entities]
  const value = choices.some((choice) => choice.id === _value) ? _value : ''
  const isMissing = !!_value && !isLoading && !isLoadingCaptureSet && !value
  useEffect(() => {
    if (isMissing) {
      onValueChange(undefined)
    }
  }, [isMissing, onValueChange])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Select.Root
          key={value}
          disabled={isLoading || choices.length === 0}
          onValueChange={onValueChange}
          value={value}
        >
          <Select.Trigger loading={isLoading}>
            <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
          </Select.Trigger>
          <Select.Content className="max-h-72">
            {choices.map((c) => (
              <Select.Item key={c.id} value={c.id}>
                {c.name}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
        {clearable && _value && (
          <Button
            aria-label={translate(STRING.CLEAR)}
            className="shrink-0 text-muted-foreground"
            onClick={() => onValueChange()}
            size="icon"
            variant="ghost"
          >
            <XIcon className="w-4 h-4" />
          </Button>
        )}
      </div>
      {captureSet?.numImages !== undefined ? (
        captureSet.numImages === 0 ? (
          <div className="flex flex-col gap-4">
            <FormMessage
              className="flex justify-between gap-4"
              message={translate(STRING.MESSAGE_CAPTURE_SET_EMPTY)}
              theme="warning"
              withIcon
            >
              {captureSet.canPopulate ? (
                <Link
                  className="font-bold"
                  to={APP_ROUTES.CAPTURE_SETS({
                    projectId: projectId as string,
                  })}
                >
                  <span>{translate(STRING.POPULATE)}</span>
                  <ChevronRight className="inline w-4 h-4 ml-2" />
                </Link>
              ) : null}
            </FormMessage>
          </div>
        ) : (
          <FormMessage
            message={translate(STRING.MESSAGE_CAPTURE_SET_COUNT, {
              total: captureSet.numImages.toLocaleString(),
            })}
            withIcon
          />
        )
      ) : null}
    </div>
  )
}
