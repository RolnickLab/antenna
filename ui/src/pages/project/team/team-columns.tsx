import { Member } from 'data-services/models/member'
import { Badge } from 'design-system/components/badge/badge'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { UserIcon } from 'lucide-react'
import { STRING, translate } from 'utils/language'
import { LeaveTeamDialog } from './leave-team-dialog'
import { ManageAccessDialog } from './manage-access-dialog'
import { RemoveMemberDialog } from './remove-member-dialog'

export const columns: (userId?: string) => TableColumn<Member>[] = (
  userId?: string
) => [
  {
    id: 'user',
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
          <span>{item.email}</span>
          {item.id === userId ? <Badge label={translate(STRING.YOU)} /> : null}
        </div>
      </BasicTableCell>
    ),
  },
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: Member) => <BasicTableCell value={item.name} />,
  },
  {
    id: 'role',
    name: translate(STRING.FIELD_LABEL_ROLE),
    renderCell: (item: Member) => <BasicTableCell value={item.role.name} />,
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
        {item.id === userId ? (
          <LeaveTeamDialog member={item} />
        ) : (
          <>
            <ManageAccessDialog member={item} />
            <RemoveMemberDialog member={item} />
          </>
        )}
      </div>
    ),
  },
]
