import { DeleteForm } from 'components/form/delete-form/delete-form'
import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { useDeleteIdentification } from 'data-services/hooks/identifications/useDeleteIdentification'
import {
  Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { IdentificationSummary } from 'design-system/components/identification/identification-summary/identification-summary'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserInfo, UserPermission } from 'utils/user/types'
import { Agree } from '../agree/agree'
import { StatusLabel } from '../status-label/status-label'
import styles from './identification-card.module.scss'

export const IdentificationCard = ({
  occurrence,
  identification,
  user,
  currentUser,
}: {
  occurrence: Occurrence
  identification: Identification
  user?: {
    id?: string
    name: string
    image?: string
  }
  currentUser?: UserInfo
}) => {
  const { projectId } = useParams()
  const [deleteIdOpen, setDeleteIdOpen] = useState(false)
  const byCurrentUser = currentUser && user?.id === currentUser.id
  const canAgree = occurrence.userPermissions.includes(UserPermission.Update)
  const canDelete = identification.userPermissions.includes(
    UserPermission.Delete
  )
  const showAgree = !byCurrentUser && canAgree
  const showDelete = canDelete
  const formattedTime = getFormatedDateTimeString({
    date: new Date(identification.createdAt),
  })

  if (deleteIdOpen) {
    return (
      <DeleteIdForm
        id={identification.id}
        onCancel={() => setDeleteIdOpen(false)}
      />
    )
  }

  return (
    <div>
      <span className={styles.timestamp}>{formattedTime}</span>
      <div className={styles.identificationCard}>
        <div className={styles.header}>
          {identification.applied && (
            <StatusLabel label={translate(STRING.ID_APPLIED)} />
          )}
          <IdentificationSummary user={user} identification={identification} />
        </div>
        <div className={styles.content}>
          <TaxonInfo
            overridden={identification.overridden}
            taxon={identification.taxon}
            getLink={(id: string) =>
              getAppRoute({
                to: APP_ROUTES.TAXON_DETAILS({
                  projectId: projectId as string,
                  taxonId: id,
                }),
              })
            }
          />
          {identification.comment && (
            <div className={styles.comment}>"{identification.comment}"</div>
          )}
          <div className={styles.actions}>
            {showAgree && (
              <Agree
                agreed={
                  currentUser ? occurrence.userAgreed(currentUser?.id) : false
                }
                agreeWith={
                  user
                    ? { identificationId: identification.id }
                    : { predictionId: identification.id }
                }
                occurrenceId={occurrence.id}
                taxonId={identification.taxon.id}
              />
            )}
            {showDelete && (
              <IconButton
                icon={IconType.RadixTrash}
                onClick={() => setDeleteIdOpen(true)}
              />
            )}
          </div>
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
  const { deleteIdentification, isLoading, isSuccess, error } =
    useDeleteIdentification()

  return (
    <div className={styles.identificationCard}>
      <DeleteForm
        error={error}
        isSuccess={isSuccess}
        isLoading={isLoading}
        type="identification"
        onCancel={onCancel}
        onSubmit={() => deleteIdentification(id)}
      />
    </div>
  )
}
