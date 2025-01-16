import { Job, SERVER_JOB_TYPES } from 'data-services/models/job'
import { Select } from 'nova-ui-kit'
import { FilterProps } from './types'

const OPTIONS = SERVER_JOB_TYPES.map((key) => {
  const typeInfo = Job.getJobTypeInfo(key)

  return {
    ...typeInfo,
  }
})

export const TypeFilter = ({ value, onAdd }: FilterProps) => (
  <Select.Root value={value ?? ''} onValueChange={onAdd}>
    <Select.Trigger>
      <Select.Value placeholder="Select a value" />
    </Select.Trigger>
    <Select.Content>
      {OPTIONS.map((option) => (
        <Select.Item key={option.key} value={option.key}>
          {option.label}
        </Select.Item>
      ))}
    </Select.Content>
  </Select.Root>
)
