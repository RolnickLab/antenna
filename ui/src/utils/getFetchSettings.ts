import { FetchSettings } from 'data-services/types'
import { TableSortSettings } from 'design-system/components/table/types'

export const getFetchSettings = ({
  columns,
  sortSettings,
}: {
  columns: { id: string; sortField?: string }[]
  sortSettings?: TableSortSettings
}): FetchSettings | undefined => {
  if (!sortSettings) {
    return undefined
  }

  const column = columns.find((c) => c.id === sortSettings?.columnId)
  if (!column?.sortField) {
    return undefined
  }

  return {
    sort: {
      field: column.sortField,
      order: sortSettings.orderBy,
    },
  }
}
