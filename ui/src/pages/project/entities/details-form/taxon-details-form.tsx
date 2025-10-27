import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { SaveButton } from 'design-system/components/button/save-button'
import { InputContent } from 'design-system/components/input/input'
import { Select } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import { RANKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type TaxonFormValues = FormValues & {
  rank: string
  parent: { id: string; name: string }
  gbif_taxon_key: string
}

const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: {
      required: true,
    },
  },
  rank: {
    label: translate(STRING.FIELD_LABEL_RANK),
  },
  parent: {
    label: translate(STRING.FIELD_LABEL_PARENT),
    rules: {
      required: true,
    },
  },
  gbif_taxon_key: {
    label: translate(STRING.FIELD_LABEL_GBIF_TAXON_KEY),
  },
}

export const TaxonDetailsForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<TaxonFormValues>({
    mode: 'onChange',
    defaultValues: {
      name: '',
      rank: 'SPECIES',
      gbif_taxon_key: '',
    },
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit({
          name: values.name,
          customFields: {
            gbif_taxon_key: values.gbif_taxon_key.length
              ? values.gbif_taxon_key
              : undefined,
            rank: values.rank,
            parent_id: values.parent.id,
          },
        })
      )}
    >
      {errorMessage && (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      )}

      <FormSection>
        <FormField name="name" type="text" config={config} control={control} />
        <FormController
          name="rank"
          control={control}
          config={config['rank']}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={config[field.name].label}
              error={fieldState.error?.message}
            >
              <RankPicker value={field.value} onValueChange={field.onChange} />
            </InputContent>
          )}
        />
        <FormController
          name="parent"
          control={control}
          config={config.parent}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={`${config[field.name].label} *`}
              error={fieldState.error?.message}
            >
              <TaxonSelect
                {...field}
                triggerLabel={field.value?.name ?? 'Select a value'}
                onTaxonChange={(taxon) => {
                  if (taxon) {
                    field.onChange({ id: taxon.id, name: taxon.name })
                  }
                }}
              />
            </InputContent>
          )}
        />
      </FormSection>
      <FormSection>
        <FormField
          name="gbif_taxon_key"
          type="text"
          config={config}
          control={control}
        />
      </FormSection>
      <FormActions>
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
      </FormActions>
    </form>
  )
}

const RankPicker = ({
  value,
  onValueChange,
}: {
  value: string
  onValueChange: (value: string) => void
}) => (
  <Select.Root value={value ?? ''} onValueChange={onValueChange}>
    <Select.Trigger>
      <Select.Value />
    </Select.Trigger>
    <Select.Content>
      {RANKS.map((rank) => (
        <Select.Item key={rank} value={rank}>
          {rank}
        </Select.Item>
      ))}
    </Select.Content>
  </Select.Root>
)
