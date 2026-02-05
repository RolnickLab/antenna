import { FormError, FormSection } from 'components/form/layout/layout'
import { useRemoveTaxaListTaxon } from 'data-services/hooks/taxa-lists/useRemoveTaxaListTaxon'
import * as Dialog from 'design-system/components/dialog/dialog'
import { CheckIcon, Loader2Icon, XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

export const RemoveTaxaListTaxonDialog = ({
  taxaListId,
  taxonId,
}: {
  taxaListId: string
  taxonId: string
}) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { removeTaxaListTaxon, isLoading, isSuccess, error } =
    useRemoveTaxaListTaxon(projectId as string)
  const errorMessage = useFormError({ error })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button
          aria-label={translate(STRING.REMOVE_TAXA_LIST_TAXON)}
          size="icon"
          variant="ghost"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        {errorMessage && (
          <FormError
            intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
            message={errorMessage}
          />
        )}
        <FormSection
          title={translate(STRING.REMOVE_TAXA_LIST_TAXON)}
          description={translate(
            STRING.MESSAGE_MESSAGE_REMOVE_TAXA_LIST_TAXON_CONFIRM
          )}
        >
          <div className="flex justify-end gap-4">
            <Button
              onClick={() => setIsOpen(false)}
              size="small"
              variant="outline"
            >
              <span>{translate(STRING.CANCEL)}</span>
            </Button>
            <Button
              disabled={isLoading || isSuccess}
              onClick={() => removeTaxaListTaxon({ taxaListId, taxonId })}
              size="small"
              variant="destructive"
            >
              <span>
                {isSuccess
                  ? translate(STRING.CONFIRMED)
                  : translate(STRING.CONFIRM)}
              </span>
              {isSuccess ? (
                <CheckIcon className="w-4 h-4" />
              ) : isLoading ? (
                <Loader2Icon className="w-4 h-4 animate-spin" />
              ) : null}
            </Button>
          </div>
        </FormSection>
      </Dialog.Content>
    </Dialog.Root>
  )
}
