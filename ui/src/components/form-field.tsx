import { useMemo } from 'react'
import {
  Controller,
  ControllerProps,
  FieldPath,
  FieldValues,
} from 'react-hook-form'
import { STRING, translate } from 'utils/language'

/* Helper component to simplify and streamline error handling in forms */
export const FormField = <
  TFieldValues extends FieldValues,
  TName extends FieldPath<TFieldValues>
>({
  rules,
  ...rest
}: Omit<ControllerProps<TFieldValues, TName>, 'rules'> & {
  rules: {
    required?: boolean
    minLength?: number
    maxLength?: number
  }
}) => {
  const controllerRules = useMemo(() => {
    const { required, minLength, maxLength } = rules

    return {
      required: required ? translate(STRING.MESSAGE_VALUE_MISSING) : undefined,
      minLength:
        minLength !== undefined
          ? {
              value: minLength,
              message: translate(STRING.MESSAGE_VALUE_MISSING),
            }
          : undefined,
      maxLength:
        maxLength !== undefined
          ? {
              value: maxLength,
              message: translate(STRING.MESSAGE_VALUE_MISSING),
            }
          : undefined,
    }
  }, [rules])

  return <Controller rules={controllerRules} {...rest} />
}
