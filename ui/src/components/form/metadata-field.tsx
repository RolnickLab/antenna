import { InputContent } from 'nova-ui-kit'
import { ControllerProps, FieldPath, FieldValues } from 'react-hook-form'
import { FormController } from './form-controller'
import { FormConfig } from './types'

/* Tall enough to show a handful of metadata entries without taking over the form. */
const VISIBLE_ROWS = 8

/**
 * Free-form JSON entry for a record's metadata, so a project can keep fields
 * the platform has no column of its own for.
 *
 * The form value is the text exactly as it was typed, not a parsed object. That
 * keeps a half-finished edit on screen while the inline error explains what is
 * wrong with it, and it preserves the key order and indentation the operator
 * chose. Text that is not a JSON object is rejected by the `validate` rule in
 * the field's config, and the form turns the text into an object on submit.
 */
export const MetadataField = <
  TFieldValues extends FieldValues,
  TName extends FieldPath<TFieldValues>
>({
  name,
  control,
  config,
}: Pick<ControllerProps<TFieldValues, TName>, 'name' | 'control'> & {
  config: FormConfig
}) => {
  const fieldConfig = config[name]

  return (
    <FormController
      name={name}
      control={control}
      config={fieldConfig}
      render={({ field, fieldState }) => (
        <InputContent
          description={fieldConfig.description}
          error={fieldState.error?.message}
          label={fieldConfig.label}
        >
          <textarea
            {...field}
            aria-invalid={!!fieldState.error}
            aria-label={fieldConfig.label}
            className="box-border w-full px-4 py-3 rounded-md border border-border bg-background text-foreground font-mono text-xs leading-5 resize-y focus:outline-none focus:border-success aria-[invalid=true]:border-destructive"
            id={field.name}
            rows={VISIBLE_ROWS}
            spellCheck={false}
            value={field.value ?? ''}
          />
        </InputContent>
      )}
    />
  )
}
