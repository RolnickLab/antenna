import { Job, SERVER_JOB_STATUS_CODES } from 'data-services/models/job'
import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { FilterProps } from './types'

const OPTIONS = SERVER_JOB_STATUS_CODES.map((code) => {
  const statusInfo = Job.getStatusInfo(code)

  return {
    ...statusInfo,
  }
}).sort((o1, o2) => o1.type - o2.type)

export const StatusFilter = ({ value, onAdd }: FilterProps) => (
  <Select.Root value={value ?? ''} onValueChange={onAdd}>
    <Select.Trigger>
      <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
    </Select.Trigger>
    <Select.Content>
      {OPTIONS.map((option) => (
        <Select.Item key={option.code} value={option.code}>
          <span className="flex items-center gap-2">
            <span
              className="w-3 h-3 rounded-full mb-0.5"
              style={{ backgroundColor: option.color }}
            />
            <span>{option.label}</span>
          </span>
        </Select.Item>
      ))}
    </Select.Content>
  </Select.Root>
)
