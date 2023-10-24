import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'
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
        <span className={styles.title}>
          {translate(STRING.ENTITY_DELETE, { type })}
        </span>
        <span className={styles.description}>
          {translate(STRING.MESSAGE_DELETE_CONFIRM, { type })}
        </span>
        <div className={styles.formActions}>
          <Button label={translate(STRING.CANCEL)} onClick={onCancel} />
          <Button
            label={
              isSuccess ? translate(STRING.DELETED) : translate(STRING.DELETE)
            }
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
