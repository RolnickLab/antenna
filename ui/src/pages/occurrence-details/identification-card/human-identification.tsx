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
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
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
    id: string
    image?: string
    name: string
  }
}) => {
  const [deleteIdOpen, setDeleteIdOpen] = useState(false)
  const formattedTime = getFormatedDateTimeString({
    date: new Date(identification.createdAt),
  })
  const byCurrentUser = currentUser && user?.id === currentUser.id
  const showDelete =
    byCurrentUser &&
    identification.userPermissions.includes(UserPermission.Update) // TODO: Update after permission PR is merged

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
              <div className="w-full">
                <TaxonDetails compact taxon={identification.taxon} />
              </div>
              <div className="flex items-center gap-2">
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
