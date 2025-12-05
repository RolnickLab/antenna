import { Member } from 'data-services/models/member'
import { Badge } from 'design-system/components/badge/badge'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { InfoIcon, UserIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
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
          {item.userId === userId ? (
            <Badge label={translate(STRING.YOU)} />
          ) : null}
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
    renderCell: (item: Member) => (
      <BasicTableCell>
        <div className="flex items-center gap-2">
          <span>{item.role.name}</span>
          {item.role.description ? (
            <BasicTooltip asChild content={item.role.description}>
              <Button size="icon" variant="ghost">
                <InfoIcon className="w-4 h-4" />
              </Button>
            </BasicTooltip>
          ) : null}
        </div>
      </BasicTableCell>
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
