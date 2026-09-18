import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { useCopyTaxaList } from 'data-services/hooks/taxa-lists/useCopyTaxaList'
import { TaxaList } from 'data-services/models/taxa-list'
import { CopyIcon } from 'lucide-react'
import { Button, Dialog, SaveButton } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

interface CopyTaxaListFormValues {
  name: string
  description: string
}

const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: { required: true },
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
}

const defaultValues = (taxaList: TaxaList): CopyTaxaListFormValues => ({
  name: `${taxaList.name} (copy)`,
  description: '',
})

export const CopyTaxaListDialog = ({ taxaList }: { taxaList: TaxaList }) => {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const {
    copyTaxaList,
    error,
    isLoading,
    isSuccess,
    reset: resetHook,
  } = useCopyTaxaList(projectId as string)
  const {
    control,
    handleSubmit,
    reset: resetForm,
    setError: setFieldError,
  } = useForm<CopyTaxaListFormValues>({
    defaultValues: defaultValues(taxaList),
  })
  const errorMessage = useFormError({
    error,
    fields: ['name'],
    setFieldError,
  })

  // Reset on open state change, so a previous attempt's error and success
  // state don't linger when the dialog is reopened.
  useEffect(() => {
    resetHook()
    resetForm(defaultValues(taxaList))
  }, [isOpen])

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <CopyIcon className="w-4 h-4" />
          <span>{translate(STRING.COPY_TO_PROJECT)}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <Dialog.Header title={translate(STRING.COPY_TO_PROJECT)} />
        {errorMessage && (
          <FormError
            inDialog
            intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
            message={errorMessage}
          />
        )}
        <form
          onSubmit={handleSubmit(async (values) => {
            const { data } = await copyTaxaList({
              taxaListId: taxaList.id,
              name: values.name,
              description: values.description,
            })
            navigate(
              getAppRoute({
                to: APP_ROUTES.TAXA_LIST_DETAILS({
                  projectId: projectId as string,
                  taxaListId: `${data.id}`,
                }),
              })
            )
          })}
        >
          <FormSection>
            <FormField
              name="name"
              type="text"
              config={config}
              control={control}
            />
            <FormField
              name="description"
              type="text"
              config={config}
              control={control}
            />
          </FormSection>
          <FormActions>
            <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
          </FormActions>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  )
}
