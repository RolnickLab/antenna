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
import { getAppRoute } from 'utils/getAppRoute'
import { UserInfo, UserPermission } from 'utils/user/types'
import { Agree } from '../agree/agree'
import { userAgreed } from '../agree/userAgreed'
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
    id: string
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
    UserPermission.Update
  )
  const showAgree = !byCurrentUser && canAgree && !identification.overridden
  const showDelete = byCurrentUser && canDelete

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
          {showAgree && (
            <Agree
              agreed={userAgreed({
                identifications: occurrence.humanIdentifications,
                taxonId: identification.taxon.id,
                userId: currentUser?.id,
              })}
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
