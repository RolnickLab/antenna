import { Member } from 'data-services/models/member'
import { Badge } from 'design-system/components/badge/badge'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { InfoIcon, UserIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { LeaveTeamDialog } from './leave-team-dialog'
import { ManageAccessDialog } from './manage-access-dialog'
import { RemoveMemberDialog } from './remove-member-dialog'

export const columns: (userId?: string) => TableColumn<Member>[] = (
  userId?: string
) => [
  {
    id: 'user',
    sortField: 'name',
    name: translate(STRING.FIELD_LABEL_USER),
    renderCell: (item: Member) => (
      <BasicTableCell>
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-12 h-12 border border-border rounded-full text-muted-foreground overflow-hidden">
            {item.image ? (
              <img className="object-cover" alt="" src={item.image} />
            ) : (
              <UserIcon className="w-4 h-4" />
            )}
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-4">
              {item.name ? (
                <span className="font-medium">{item.name}</span>
              ) : null}
              {item.userId === userId ? (
                <Badge label={translate(STRING.YOU)} />
              ) : null}
            </div>
            <span>{item.email}</span>
          </div>
        </div>
      </BasicTableCell>
    ),
  },
  {
    id: 'role',
    name: translate(STRING.FIELD_LABEL_ROLE),
    renderCell: (item: Member) => (
      <BasicTableCell>
        <div className="flex items-center gap-2">
          <span>{item.role.name}</span>
          {item.role.description ? (
            <BasicTooltip asChild content={item.role.description}>
              <Button
                aria-label={translate(STRING.ABOUT_ROLE)}
                size="icon"
                variant="ghost"
              >
                <InfoIcon className="w-4 h-4" />
              </Button>
            </BasicTooltip>
          ) : null}
        </div>
      </BasicTableCell>
    ),
  },
  {
    id: 'added-at',
    name: translate(STRING.FIELD_LABEL_ADDED_AT),
    sortField: 'created_at',
    renderCell: (item: Member) => (
      <BasicTableCell
        value={getFormatedDateString({ date: item.addedAt })}
        details={[getFormatedTimeString({ date: item.addedAt })]}
      />
    ),
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Member) => (
      <BasicTableCell
        value={
          item.updatedAt
            ? getFormatedDateString({ date: item.updatedAt })
            : undefined
        }
        details={
          item.updatedAt
            ? [getFormatedTimeString({ date: item.updatedAt })]
            : undefined
        }
      />
    ),
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Member) => (
      <div className="p-4 flex items-center justify-end gap-2">
        {item.userId === userId ? (
          item.canDelete ? (
            <LeaveTeamDialog member={item} />
          ) : null
        ) : (
          <>
            {item.canUpdate ? <ManageAccessDialog member={item} /> : null}
            {item.canDelete ? <RemoveMemberDialog member={item} /> : null}
          </>
        )}
      </div>
    ),
  },
]
