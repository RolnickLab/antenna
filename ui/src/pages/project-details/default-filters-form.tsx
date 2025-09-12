import { FormController } from 'components/form/form-controller'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { AddTaxon } from 'components/taxon-search/add-taxon'
import { TaxonSelect } from 'components/taxon-search/taxon-select'
import { ProjectDetails } from 'data-services/models/project-details'
import { InputContent } from 'design-system/components/input/input'
import { CheckIcon, Loader2Icon, XIcon } from 'lucide-react'
import { Button, Slider } from 'nova-ui-kit'
import { Fragment } from 'react'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

interface DefaultFiltersFormValues {
  scoreThreshold: number
  includeTaxa: { id: string; name: string }[]
  excludeTaxa: { id: string; name: string }[]
}

const config: FormConfig = {
  scoreThreshold: {
    label: 'Score threshold',
    description:
      'Occurrences with a score below this threshold will be exluded by default for the project.',
  },
  includeTaxa: {
    label: 'Include taxa',
    description: 'This taxa will be included by default for the project.',
  },
  excludeTaxa: {
    label: 'Exclude taxa',
    description: 'This taxa will be excluded by default for the project.',
  },
}

export const DefaultFiltersForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
  project,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (data: DefaultFiltersFormValues) => void
  project: ProjectDetails
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<DefaultFiltersFormValues>({
    defaultValues: {
      scoreThreshold: project.settings.scoreThreshold,
      includeTaxa: project.settings.includeTaxa,
      excludeTaxa: project.settings.excludeTaxa,
    },
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) => {
        onSubmit(values)
      })}
    >
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
                    value={[field.value]}
                    onValueChange={(value) => field.onChange(value[0])}
                    onValueCommit={(value) => field.onChange(value[0])}
                  />
                  <span className="w-12 text-right body-overline text-muted-foreground">
                    {field.value}
                  </span>
                </div>
              </InputContent>
            )}
          />
        </FormRow>
      </FormSection>
      <FormSection
        title="Taxa"
        style={
          project.featureFlags.default_filters ? undefined : { display: 'none' }
        }
      >
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
                <TaxaSelect
                  taxa={field.value}
                  onTaxaChange={field.onChange}
                  limit={5}
                />
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
                <TaxaSelect
                  taxa={field.value}
                  onTaxaChange={field.onChange}
                  limit={5}
                />
              </InputContent>
            )}
          />
        </FormRow>
      </FormSection>
      <FormActions>
        <Button size="small" type="submit" variant="success">
          <span>
            {isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}
          </span>
          {isSuccess ? (
            <CheckIcon className="w-4 h-4 ml-2" />
          ) : isLoading ? (
            <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
          ) : null}
        </Button>
      </FormActions>
    </form>
  )
}

const TaxaSelect = ({
  limit,
  onTaxaChange,
  taxa = [],
}: {
  limit?: number
  onTaxaChange: (taxa: { id: string; name: string }[]) => void
  taxa?: { id: string; name: string }[]
}) => {
  const canAdd = limit ? taxa.length < limit : true

  return (
    <div
      className="grid items-center gap-x-2 gap-y-4"
      style={{ gridTemplateColumns: '1fr auto' }}
    >
      {taxa.map((taxon) => (
        <Fragment key={taxon.id}>
          <TaxonSelect
            triggerLabel={taxon.name}
            onTaxonChange={(t) => {
              if (t) {
                taxon.id = t.id
                taxon.name = t.name
                onTaxaChange([...taxa])
              }
            }}
          />
          <Button
            className="shrink-0 text-muted-foreground"
            onClick={() => onTaxaChange(taxa.filter((t) => t.id !== taxon.id))}
            size="icon"
            type="button"
            variant="ghost"
          >
            <XIcon className="w-4 h-4" />
          </Button>
        </Fragment>
      ))}
      {canAdd ? (
        <AddTaxon
          onAdd={(t) => {
            if (t) {
              onTaxaChange([...taxa, { id: t.id, name: t.name }])
            }
          }}
        />
      ) : null}
    </div>
  )
}
