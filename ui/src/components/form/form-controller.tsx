import { useMemo } from 'react'
import {
  Controller,
  ControllerProps,
  FieldPath,
  FieldValues,
} from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { FieldConfig } from './types'

/* Helper component to simplify and streamline error handling in forms */
export const FormController = <
  TFieldValues extends FieldValues,
  TName extends FieldPath<TFieldValues>
>({
  name,
  config,
  ...rest
}: Omit<ControllerProps<TFieldValues, TName>, 'rules'> & {
  config: FieldConfig
}) => {
  const { rules = {} } = config

  const controllerRules = useMemo(() => {
    const { required, minLength, maxLength, min, max } = rules

    return {
      required: required ? translate(STRING.MESSAGE_VALUE_MISSING) : undefined,
      minLength:
        minLength !== undefined
          ? {
              value: minLength,
              message: translate(STRING.MESSAGE_VALUE_INVALID),
            }
          : undefined,
      maxLength:
        maxLength !== undefined
          ? {
              value: maxLength,
              message: translate(STRING.MESSAGE_VALUE_INVALID),
            }
          : undefined,
      min:
        min !== undefined
          ? {
              value: min,
              message: translate(STRING.MESSAGE_VALUE_INVALID),
            }
          : undefined,
      max:
        max !== undefined
          ? {
              value: max,
              message: translate(STRING.MESSAGE_VALUE_INVALID),
            }
          : undefined,
    }
  }, [rules])

  return <Controller name={name} rules={controllerRules} {...rest} />
}
