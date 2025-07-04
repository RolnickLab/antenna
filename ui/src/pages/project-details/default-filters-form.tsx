import { FormController } from 'components/form/form-controller'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { Project } from 'data-services/models/project'
import { InputContent } from 'design-system/components/input/input'
import { Button, Slider } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

interface DefaultFiltersFormValues {
  scoreThreshold?: any
  includeTaxa?: any
  excludeTaxa?: any
}

const config: FormConfig = {
  scoreThreshold: {
    label: 'Score threshold',
    description:
      'Occurrences with a score below the threshold will be exluded by default for the project.',
    rules: {
      required: true,
    },
  },
  includeTaxa: {
    label: 'Include taxa',
    description: 'This taxa will be included by default for the project.',
    rules: {
      required: true,
    },
  },
  excludeTaxa: {
    label: 'Exclude taxa',
    description: 'This taxa will be excluded by default for the project.',
    rules: {
      required: true,
    },
  },
}

export const DefaultFiltersForm = ({
  error,
  onSubmit,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  project: Project
  onSubmit: (data: DefaultFiltersFormValues) => void
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<DefaultFiltersFormValues>({
    defaultValues: {},
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form onSubmit={handleSubmit((values) => onSubmit(values))}>
      {errorMessage && (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      )}
      <FormSection title="Occurrences">
        <FormRow>
          <FormController
            name="scoreThreshold"
            control={control}
            config={config.scoreThreshold}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <div className="w-full h-12 flex items-center">
                  <Slider
                    invertedColors
                    min={0}
                    max={1}
                    step={0.01}
                    value={[0.6]}
                    onValueChange={() => {}}
                    onValueCommit={() => {}}
                  />
                  <span className="w-12 text-right body-overline text-muted-foreground">
                    0.6
                  </span>
                </div>
              </InputContent>
            )}
          />
        </FormRow>
      </FormSection>
      <FormSection title="Taxa">
        <FormRow>
          <FormController
            name="includeTaxa"
            control={control}
            config={config.includeTaxa}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <div className="space-y-4">
                  <div>
                    <TaxonSelect
                      triggerLabel="Lepidoptera"
                      onTaxonChange={() => {}}
                    />
                  </div>
                </div>
              </InputContent>
            )}
          />
          <FormController
            name="excludeTaxa"
            control={control}
            config={config.excludeTaxa}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <div className="space-y-4">
                  <div>
                    <TaxonSelect
                      triggerLabel="Not Lepidoptera"
                      onTaxonChange={() => {}}
                    />
                  </div>
                  <div>
                    <TaxonSelect
                      triggerLabel="Not identifieable"
                      onTaxonChange={() => {}}
                    />
                  </div>
                </div>
              </InputContent>
            )}
          />
        </FormRow>
      </FormSection>
      <FormActions>
        <Button type="submit" size="small" variant="success">
          <span>Save</span>
        </Button>
      </FormActions>
    </form>
  )
}
