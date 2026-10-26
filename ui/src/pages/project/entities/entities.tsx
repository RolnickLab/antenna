import { useEntities } from 'data-services/hooks/entities/useEntities'
import {
  PageHeader,
  PaginationBar,
  Table,
  TableSortSettings,
} from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { columns } from './entities-columns'
import { NewEntityDialog } from './new-entity-dialog'

export const Entities = ({
  title,
  collection,
  type,
  tooltip,
}: {
  title: string
  collection: string
  type: string
  tooltip?: string
}) => {
  const { projectId } = useParams()
  const [sort, setSort] = useState<TableSortSettings | undefined>({
    field: 'created_at',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const { entities, userPermissions, total, isLoading, isFetching, error } =
    useEntities(collection, {
      projectId,
      pagination,
      sort,
    })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <PageHeader
        title={title}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        tooltip={tooltip}
      >
        {canCreate && (
          <NewEntityDialog collection={collection} type={type} isCompact />
        )}
      </PageHeader>
      <Table
        columns={columns({ collection, type })}
        error={error}
        isLoading={isLoading}
        items={entities}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      {entities?.length ? (
        <PaginationBar
          compact
          pagination={pagination}
          setPage={setPage}
          total={total}
        />
      ) : null}
    </>
  )
}
