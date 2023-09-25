import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { useUserInfo } from 'data-services/hooks/auth/useUserInfo'
import { useDeleteIdentification } from 'data-services/hooks/identifications/useDeleteIdentification'
import {
  Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { IdentificationSummary } from 'design-system/components/identification/identification-summary/identification-summary'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { Agree } from '../agree/agree'
import { StatusLabel } from '../status-label/status-label'
import styles from './identification-card.module.scss'

export const IdentificationCard = ({
  occurrence,
  identification,
  user,
}: {
  occurrence: Occurrence
  identification: Identification
  user?: {
    id: string
    name: string
    image?: string
  }
}) => {
  const [deleteIdOpen, setDeleteIdOpen] = useState(false)
  const { userInfo } = useUserInfo()
  const { projectId } = useParams()
  const byCurrentUser = user?.id === userInfo?.id

  if (deleteIdOpen) {
    return (
      <DeleteIdForm
        id={identification.id}
        onCancel={() => setDeleteIdOpen(false)}
      />
    )
  }

  return (
    <div className={styles.identificationCard}>
      <div className={styles.content}>
        <IdentificationSummary user={user}>
          {identification.applied && <StatusLabel label="ID applied" />}
          <TaxonInfo
            overridden={identification.overridden}
            taxon={identification.taxon}
            getLink={(id: string) =>
              getAppRoute({
                to: APP_ROUTES.SPECIES_DETAILS({
                  projectId: projectId as string,
                  speciesId: id,
                }),
              })
            }
          />
        </IdentificationSummary>
        <div className={styles.actions}>
          {byCurrentUser ? (
            <IconButton
              icon={IconType.RadixTrash}
              onClick={() => setDeleteIdOpen(true)}
            />
          ) : (
            <Agree occurrence={occurrence} taxonId={identification.taxon.id} />
          )}
        </div>
      </div>
    </div>
  )
}

const DeleteIdForm = ({
  id,
  onCancel,
}: {
  id: string
  onCancel: () => void
}) => {
  const { deleteIdentification, isLoading, error, isSuccess } =
    useDeleteIdentification()

  const formError = error ? parseServerError(error)?.message : undefined

  return (
    <div className={styles.identificationCard}>
      {formError ? (
        <div className={styles.deleteFormError}>
          <span>{formError}</span>
        </div>
      ) : null}
      <div className={styles.content}>
        <span className={styles.deleteFormTitle}>Delete identification</span>
        <span className={styles.deleteFormDescription}>
          Are you sure you want to delete this identification?
        </span>
        <div className={styles.deleteFormActions}>
          <Button label="Cancel" onClick={onCancel} />
          <Button
            label={isSuccess ? 'Deleted' : 'Delete'}
            icon={isSuccess ? IconType.RadixCheck : undefined}
            theme={ButtonTheme.Destructive}
            loading={isLoading}
            onClick={() => deleteIdentification(id)}
          />
        </div>
      </div>
    </div>
  )
}
