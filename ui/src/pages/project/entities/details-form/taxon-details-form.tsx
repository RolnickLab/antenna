import { FormController } from 'components/form/form-controller'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { GBIFSelect } from 'components/gbif/gbif-select'
import { GBIFTaxon } from 'components/gbif/types'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { SaveButton } from 'design-system/components/button/save-button'
import { InputContent } from 'design-system/components/input/input'
import { InfoIcon } from 'lucide-react'
import { Select } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import { RANKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps } from './types'

type TaxonFormValues = {
  rank: string
  name?: GBIFTaxon
  parent?: { id: string; name: string }
}

const config: FormConfig = {
  rank: {
    label: translate(STRING.FIELD_LABEL_RANK),
    description:
      'Specify the taxon rank. The rank will affect the GBIF search results.',
  },
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    description: 'Specify the taxon name, based on GBIF search results.',
    rules: {
      required: true,
    },
  },
  parent: {
    label: translate(STRING.FIELD_LABEL_PARENT),
    description:
      'Specify the taxon parent, based on Antenna search results. If the parent does not exist on Antenna, please add it first.',
    rules: {
      required: true,
    },
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
    setValue,
    watch,
  } = useForm<TaxonFormValues>({
    mode: 'onChange',
    defaultValues: {
      rank: 'SPECIES',
    },
  })

  const rank = watch('rank')
  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit({
          name: values.name?.canonicalName,
          customFields: {
            gbif_taxon_key: values.name?.key,
            parent_id: values.parent?.id,
            rank: values.rank,
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
        <div className="flex gap-4 p-4 border border-border rounded-md">
          <InfoIcon className="shrink-0 w-4 h-4 text-muted-foreground" />
          <p className="body-small text-muted-foreground">
            From this form you can add missing taxa to Antenna. Since taxa are
            shared across projects, names are currently restricted to the{' '}
            <a
              className="text-primary font-semibold"
              href="https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
              rel="noreferrer"
              target="_blank"
            >
              GBIF Backbone Taxonomy
            </a>
            . One other restriction is that taxa have to be added one by one. We
            are working on a more flexible workflow for taxa. Please reach out
            to the team if you have custom requests in the meantime.
          </p>
        </div>
        <FormRow>
          <FormController
            name="rank"
            control={control}
            config={config['rank']}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={`${config[field.name].label} *`}
                error={fieldState.error?.message}
              >
                <RankPicker
                  value={field.value}
                  onValueChange={(value) => {
                    field.onChange(value)
                    setValue('name', undefined) // Reset GBIF taxon if rank is updated
                  }}
                />
              </InputContent>
            )}
          />
          <FormController
            name="name"
            control={control}
            config={config.name}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={`${config[field.name].label} *`}
                error={fieldState.error?.message}
              >
                <GBIFSelect
                  rank={rank}
                  onTaxonChange={(taxon) => {
                    if (taxon) {
                      field.onChange(taxon)
                    }
                  }}
                  triggerLabel={field.value?.canonicalName ?? 'Select a value'}
                />
              </InputContent>
            )}
          />
        </FormRow>
        <FormRow>
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
                  onTaxonChange={(taxon) => {
                    if (taxon) {
                      field.onChange({ id: taxon.id, name: taxon.name })
                    }
                  }}
                  triggerLabel={field.value?.name ?? 'Select a value'}
                />
              </InputContent>
            )}
          />
        </FormRow>
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
