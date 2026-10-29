import { Checkbox, Input, InputContent, Select } from 'nova-ui-kit'
import { Control, Controller } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { EntitySelect } from './entity-select'
import { FieldDescriptor, validateNumber } from './schema-to-fields'

// Labels and help text come from the server schema and are shown as received.
export const SchemaField = ({
  control,
  field,
  formName,
  projectId,
  onLabelChange,
}: {
  control: Control<any>
  field: FieldDescriptor
  formName: string
  projectId: string
  onLabelChange?: (label?: string) => void
}) => (
  <Controller
    control={control}
    name={formName}
    rules={{
      required: field.required
        ? translate(STRING.MESSAGE_VALUE_MISSING)
        : undefined,
      validate: (value) => {
        if (field.kind === 'integer' || field.kind === 'number') {
          return validateNumber(field, value)
        }
        if (field.kind === 'json' && value) {
          try {
            JSON.parse(`${value}`)
          } catch {
            return translate(STRING.MESSAGE_VALUE_INVALID)
          }
        }
        return undefined
      },
    }}
    render={({ field: controller, fieldState }) => {
      const label = field.required ? `${field.label} *` : field.label
      const notSet = field.required
        ? undefined
        : translate(STRING.JOB_VALUE_NOT_SET)
      const error = fieldState.error?.message

      switch (field.kind) {
        case 'boolean':
          return (
            <InputContent
              label=""
              description={field.description}
              error={error}
            >
              <Checkbox
                checked={controller.value ?? false}
                id={formName}
                label={label}
                onCheckedChange={controller.onChange}
              />
            </InputContent>
          )
        case 'entity':
          return (
            <InputContent
              label={label}
              description={field.description}
              error={error}
            >
              <EntitySelect
                entity={field.entity as string}
                entityFilters={field.entityFilters}
                projectId={projectId}
                label={field.label}
                placeholder={notSet}
                value={controller.value}
                onValueChange={(value, optionLabel) => {
                  controller.onChange(value)
                  onLabelChange?.(optionLabel)
                }}
              />
            </InputContent>
          )
        case 'select':
          return (
            <InputContent
              label={label}
              description={field.description}
              error={error}
            >
              <Select.Root
                value={controller.value ?? ''}
                onValueChange={controller.onChange}
              >
                <Select.Trigger aria-label={field.label}>
                  <Select.Value
                    placeholder={translate(STRING.SELECT_PLACEHOLDER)}
                  />
                </Select.Trigger>
                <Select.Content>
                  {field.options?.map((option) => (
                    <Select.Item key={option} value={`${option}`}>
                      {option}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </InputContent>
          )
        case 'json':
          return (
            <InputContent
              label={label}
              description={field.description}
              error={error}
            >
              <textarea
                className="w-full min-h-[80px] p-2 rounded-md border border-border bg-background body-small font-mono"
                {...controller}
                placeholder={notSet}
                value={controller.value ?? ''}
              />
            </InputContent>
          )
        default:
          return (
            <Input
              {...controller}
              value={controller.value ?? ''}
              description={field.description}
              error={error}
              label={label}
              placeholder={field.kind === 'integer-list' ? '1, 2, 3' : notSet}
              type={
                field.kind === 'integer' || field.kind === 'number'
                  ? 'number'
                  : 'text'
              }
              step={field.kind === 'integer' ? 1 : undefined}
            />
          )
      }
    }}
  />
)
