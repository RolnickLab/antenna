import { IdentificationFieldValues } from './types'
import { useCreateIdentification } from './useCreateIdentification'

export const useCreateIdentifications = (
  params: IdentificationFieldValues[]
) => {
  const { createIdentification, isLoading, isSuccess } =
    useCreateIdentification()

  return {
    isLoading,
    isSuccess,
    createIdentifications: async () => {
      const promises = params.map((variables) =>
        createIdentification(variables)
      )
      await Promise.all(promises)
    },
  }
}
