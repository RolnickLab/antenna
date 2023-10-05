import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { FormError } from '../layout/layout'
import styles from './delete-form.module.scss'

export const DeleteForm = ({
  type,
  error,
  isLoading,
  isSuccess,
  onCancel,
  onSubmit,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  type: string
  onCancel: () => void
  onSubmit: () => void
}) => {
  const errorMessage = error ? parseServerError(error)?.message : undefined

  return (
    <>
      {errorMessage ? (
        <FormError message={errorMessage} style={{ padding: '8px 16px' }} />
      ) : null}
      <div className={styles.content}>
        <span className={styles.title}>Delete {type}</span>
        <span className={styles.description}>
          Are you sure you want to delete this {type}?
        </span>
        <div className={styles.formActions}>
          <Button label="Cancel" onClick={onCancel} />
          <Button
            label={isSuccess ? 'Deleted' : 'Delete'}
            icon={isSuccess ? IconType.RadixCheck : undefined}
            theme={ButtonTheme.Destructive}
            loading={isLoading}
            onClick={onSubmit}
          />
        </div>
      </div>
    </>
  )
}
