import { FormMessage } from 'components/form/layout/layout'
import { useCaptureSets } from 'data-services/hooks/capture-sets/useCaptureSets'
import { ChevronRight } from 'lucide-react'
import { Select } from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const CaptureSetPicker = ({
  value: _value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { captureSets = [], isLoading } = useCaptureSets({
    projectId: projectId as string,
  })
  const captureSet = captureSets.find((c) => c.id === _value)
  const value = captureSet ? _value : ''

  return (
    <div className="flex flex-col gap-4">
      <Select.Root
        key={value}
        disabled={isLoading || captureSets.length === 0}
        onValueChange={onValueChange}
        value={value}
      >
        <Select.Trigger loading={isLoading}>
          <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
        </Select.Trigger>
        <Select.Content className="max-h-72">
          {captureSets.map((c) => (
            <Select.Item key={c.id} value={c.id}>
              {c.name}
            </Select.Item>
          ))}
        </Select.Content>
      </Select.Root>
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
