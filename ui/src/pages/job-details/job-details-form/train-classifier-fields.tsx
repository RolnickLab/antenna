import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import { FormMessage, FormRow } from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { API_ROUTES } from 'data-services/constants'
import { useAlgorithms } from 'data-services/hooks/algorithm/useAlgorithms'
import { useTrainingSummary } from 'data-services/hooks/algorithm/useTrainingSummary'
import { EntityPicker, InputContent, Select } from 'nova-ui-kit'
import { Control, useWatch } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import {
  JobFormValues,
  TRAINING_DATA_INAT,
  TRAINING_DATA_PROJECT,
  TRAINING_DATA_PROJECT_AND_INAT,
} from './types'

const toNumber = (value?: number | string) => {
  const parsed = Number(value)
  return value === undefined || value === '' || isNaN(parsed)
    ? undefined
    : parsed
}

export const TrainClassifierFields = ({
  config,
  control,
}: {
  config: FormConfig
  control: Control<JobFormValues>
}) => {
  const { projectId } = useParams()
  const values = useWatch({ control })
  const usesProjectData = values.dataSource !== TRAINING_DATA_INAT
  const { summary: projectSummary } = useTrainingSummary({
    algorithm: values.algorithmKey,
    minPerSpecies: toNumber(values.minPerSpecies),
    occurrenceSet: values.occurrenceSet,
    projectId,
    testFraction: toNumber(values.testFraction),
  })
  // Offline data alone has no project rows to count.
  const summary = usesProjectData ? projectSummary : undefined

  return (
    <>
      <FormRow>
        <FormController
          name="algorithmKey"
          control={control}
          config={config['algorithmKey']}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={`${config[field.name].label} *`}
              error={fieldState.error?.message}
            >
              <TrainableAlgorithmPicker
                value={field.value}
                onValueChange={field.onChange}
              />
            </InputContent>
          )}
        />
        <FormController
          name="occurrenceSet"
          control={control}
          config={config['occurrenceSet']}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={config[field.name].label}
              error={fieldState.error?.message}
            >
              <EntityPicker
                collection={API_ROUTES.OCCURRENCE_SET_CHOICES}
                onValueChange={field.onChange}
                value={field.value}
              />
            </InputContent>
          )}
        />
      </FormRow>
      <FormRow>
        <FormController
          name="dataSource"
          control={control}
          config={config['dataSource']}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={config[field.name].label}
              error={fieldState.error?.message}
            >
              <TrainingDataPicker
                value={field.value}
                onValueChange={field.onChange}
              />
            </InputContent>
          )}
        />
        <FormController
          name="taxaList"
          control={control}
          config={config['taxaList']}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={`${config[field.name].label}${
                usesProjectData ? '' : ' *'
              }`}
              error={fieldState.error?.message}
            >
              <EntityPicker
                collection={API_ROUTES.TAXA_LISTS}
                onValueChange={field.onChange}
                value={field.value}
              />
            </InputContent>
          )}
        />
      </FormRow>
      <FormRow>
        <FormField
          name="testFraction"
          type="number"
          step={0.05}
          config={config}
          control={control}
        />
        <FormField
          name="minPerSpecies"
          type="number"
          config={config}
          control={control}
        />
      </FormRow>
      {summary ? (
        summary.numRows === 0 ? (
          <FormMessage
            message={translate(STRING.MESSAGE_TRAINING_DATA_EMPTY)}
            theme="warning"
            withIcon
          />
        ) : (
          <FormMessage
            message={translate(STRING.MESSAGE_TRAINING_DATA_COUNT, {
              classes: `${summary.numClasses}`,
              occurrences: summary.numOccurrences.toLocaleString(),
              rows: summary.numRows.toLocaleString(),
              test: summary.numTest.toLocaleString(),
              train: summary.numTrain.toLocaleString(),
            })}
            withIcon
          />
        )
      ) : null}
      {summary && summary.numWithoutEmbedding > 0 ? (
        <FormMessage
          message={translate(STRING.MESSAGE_TRAINING_DATA_MISSING_EMBEDDINGS, {
            total: summary.numWithoutEmbedding.toLocaleString(),
          })}
          theme="warning"
          withIcon
        />
      ) : null}
    </>
  )
}

export const TrainableAlgorithmPicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value: string) => void
}) => {
  const { projectId } = useParams()
  const { algorithms = [], isLoading } = useAlgorithms({
    projectId: projectId as string,
    filters: [{ field: 'trainable', value: 'true' }],
  })

  return (
    <Select.Root
      disabled={isLoading || algorithms.length === 0}
      value={value ?? ''}
      onValueChange={onValueChange}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {algorithms.map((algorithm) => (
          <Select.Item key={algorithm.key} value={algorithm.key}>
            {algorithm.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}

const TrainingDataPicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value: string) => void
}) => {
  const options = [
    {
      value: TRAINING_DATA_PROJECT,
      label: translate(STRING.TRAINING_DATA_PROJECT),
    },
    {
      value: TRAINING_DATA_PROJECT_AND_INAT,
      label: translate(STRING.TRAINING_DATA_PROJECT_AND_INAT),
    },
    { value: TRAINING_DATA_INAT, label: translate(STRING.TRAINING_DATA_INAT) },
  ]

  return (
    <Select.Root value={value ?? ''} onValueChange={onValueChange}>
      <Select.Trigger>
        <Select.Value />
      </Select.Trigger>
      <Select.Content>
        {options.map((option) => (
          <Select.Item key={option.value} value={option.value}>
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
