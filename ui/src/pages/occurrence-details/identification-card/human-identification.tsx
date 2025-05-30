import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteIdentification } from 'data-services/hooks/identifications/useDeleteIdentification'
import {
  HumanIdentification as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { TrashIcon, UserIcon } from 'lucide-react'
import {
  Box,
  Button,
  IdentificationCard,
  IdentificationDetails,
  TaxonDetails,
} from 'nova-ui-kit'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getAppRoute } from 'utils/getAppRoute'
import { UserInfo, UserPermission } from 'utils/user/types'
import { Agree } from '../agree/agree'

export const HumanIdentification = ({
  currentUser,
  identification,
  occurrence,
  user,
}: {
  currentUser?: UserInfo
  identification: Identification
  occurrence: Occurrence
  user: {
    id?: string
    image?: string
    name: string
  }
}) => {
  const { projectId } = useParams()
  const [deleteIdOpen, setDeleteIdOpen] = useState(false)
  const formattedTime = getFormatedDateTimeString({
    date: new Date(identification.createdAt),
  })
  const byCurrentUser = currentUser && user?.id === currentUser.id
  const canAgree = occurrence.userPermissions.includes(UserPermission.Update)
  const canDelete = identification.userPermissions.includes(
    UserPermission.Delete
  )
  const showAgree = !byCurrentUser && canAgree
  const showDelete = byCurrentUser && canDelete

  return (
    <div>
      <span className="block p-2 text-right text-muted-foreground body-overline-small normal-case">
        {formattedTime}
      </span>
      {deleteIdOpen ? (
        <DeleteIdForm
          id={identification.id}
          onCancel={() => setDeleteIdOpen(false)}
        />
      ) : (
        <IdentificationCard
          avatar={
            user.image?.length ? (
              <img alt="" src={user.image} />
            ) : (
              <UserIcon className="w-4 h-4 text-generic-white" />
            )
          }
          title={user.name}
        >
          <IdentificationDetails
            applied={identification.applied}
            className="border-border border-t"
          >
            <div className="w-full flex flex-col items-end gap-4">
              <Link
                className="w-full"
                to={getAppRoute({
                  to: APP_ROUTES.TAXON_DETAILS({
                    projectId: projectId as string,
                    taxonId: identification.taxon.id,
                  }),
                })}
              >
                <TaxonDetails compact taxon={identification.taxon} />
              </Link>
              {identification.comment ? (
                <p className="w-full body-small italic text-muted-foreground">
                  "{identification.comment}"
                </p>
              ) : null}
              <div className="flex items-center gap-2">
                {showAgree && (
                  <Agree
                    agreed={
                      currentUser
                        ? occurrence.userAgreed(
                            currentUser.id,
                            identification.taxon.id
                          )
                        : false
                    }
                    agreeWith={{ predictionId: identification.id }}
                    applied={identification.applied}
                    occurrenceId={occurrence.id}
                    taxonId={identification.taxon.id}
                  />
                )}
                {showDelete && (
                  <Button
                    onClick={() => setDeleteIdOpen(true)}
                    size="icon"
                    variant="ghost"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
          </IdentificationDetails>
        </IdentificationCard>
      )}
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
    <Box className="p-0">
      <DeleteForm
        error={error}
        isSuccess={isSuccess}
        isLoading={isLoading}
        type="identification"
        onCancel={onCancel}
        onSubmit={() => deleteIdentification(id)}
      />
    </Box>
  )
}
