import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import styles from './id-quick-actions.module.scss'

interface IdButtonProps {
  occurrenceId: string
  applied: boolean
  label: string
  value: string
}

export const IdButton = ({
  occurrenceId,
  applied,
  label,
  value,
}: IdButtonProps) => {
  const { createIdentification, isLoading, isSuccess } =
    useCreateIdentification()

  return (
    <Button
      label={label}
      icon={isSuccess || applied ? IconType.RadixCheck : undefined}
      loading={isLoading}
      disabled={isSuccess || applied}
      customClass={styles.idButton}
      onClick={() =>
        createIdentification({
          occurrenceId,
          taxonId: value,
        })
      }
    />
  )
}
