import { Input } from 'design-system/components/input/input'
import { FocusEvent } from 'react'
import { ControllerProps, FieldPath, FieldValues } from 'react-hook-form'
import { FormController } from './form-controller'
import { FormConfig } from './types'

/* Helper component to simplify and streamline form field logic */
export const FormField = <
  TFieldValues extends FieldValues,
  TName extends FieldPath<TFieldValues>
>({
  name,
  control,
  config,
  type,
  step,
  noArrows,
  onBlur,
}: Pick<ControllerProps<TFieldValues, TName>, 'name' | 'control'> & {
  config: FormConfig
  type?: 'number' | 'text' | 'password'
  step?: number
  noArrows?: boolean
  onBlur?: (e: FocusEvent<HTMLInputElement>) => void
}) => {
  const fieldConfig = config[name]

  return (
    <FormController
      name={name}
      control={control}
      config={fieldConfig}
      render={({ field, fieldState }) => (
        <Input
          {...field}
          type={type}
          label={
            fieldConfig.rules?.required
              ? `${fieldConfig.label} *`
              : fieldConfig.label
          }
          description={fieldConfig.description}
          error={fieldState.error?.message}
          step={step}
          noArrows={noArrows}
          onBlur={(e) => {
            onBlur?.(e)
            field.onBlur()
          }}
        />
      )}
    />
  )
}
