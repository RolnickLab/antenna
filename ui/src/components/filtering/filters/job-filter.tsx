import { API_ROUTES } from 'data-services/constants'
import { useEntities } from 'data-services/hooks/entities/useEntities'
import { useJobChoice } from 'data-services/hooks/jobs/useJobChoice'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { FilterProps } from './types'

type JobOption = { id: string; name: string }

const getLabel = (job: JobOption) => `${job.name} (#${job.id})`

export const JobFilter = ({ onAdd, onClear, value }: FilterProps) => {
  const { projectId } = useParams()
  const { entities = [], isLoading } = useEntities(API_ROUTES.JOB_CHOICES, {
    projectId: projectId as string,
  })
  const options: JobOption[] = entities.map((e) => ({ id: e.id, name: e.name }))
  const missing = !!value && !isLoading && !options.some((o) => o.id === value)

  // A job linked from its details page may be older than the listed choices.
  const { job: selectedJob } = useJobChoice(value, missing)
  if (missing && selectedJob) {
    options.push(selectedJob)
  }

  return (
    <Select.Root
      key={value}
      disabled={isLoading || options.length === 0}
      onValueChange={(value) => (value ? onAdd(value) : onClear())}
      value={options.some((o) => o.id === value) ? value : ''}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {options.map((o) => (
          <Select.Item key={o.id} value={o.id}>
            {getLabel(o)}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
