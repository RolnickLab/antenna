import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useSessions } from 'data-services/hooks/sessions/useSessions'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { FilterSettings } from '../../components/filter-settings/filter-settings'
import { columns } from './session-columns'
import { SessionGallery } from './session-gallery'
import styles from './sessions.module.scss'

export const Sessions = () => {
  const { projectId } = useParams()

  const [columnSettings, setColumnSettings] = useState<{
    [id: string]: boolean
  }>({
    deployment: true,
    snapshots: true,
    session: true,
    images: true,
    duration: true,
    captures: true,
    occurrences: false,
    species: true,
  })
  const { sort, setSort } = useSort()
  const { pagination, setPage } = usePagination()
  const { filters } = useFilters()
  const { sessions, total, isLoading, isFetching, error } = useSessions({
    projectId,
    sort,
    pagination,
    filters,
  })
  const { selectedView, setSelectedView } = useSelectedView('table')

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      <div className={styles.infoWrapper}>
        {isFetching && <FetchInfo isLoading={isLoading} />}
        <FilterSettings />
      </div>
      <Tabs.Root value={selectedView} onValueChange={setSelectedView}>
        <Tabs.List>
          <Tabs.Trigger
            value="table"
            label={translate(STRING.TAB_ITEM_TABLE)}
            icon={IconType.TableView}
          />
          <Tabs.Trigger
            value="gallery"
            label={translate(STRING.TAB_ITEM_GALLERY)}
            icon={IconType.GalleryView}
          />
        </Tabs.List>
        <Tabs.Content value="table">
          <div className={styles.tableContent}>
            <div className={styles.settingsWrapper}>
              <ColumnSettings
                columns={columns(projectId as string)}
                columnSettings={columnSettings}
                onColumnSettingsChange={setColumnSettings}
              />
            </div>
            <Table
              items={sessions}
              isLoading={isLoading}
              columns={columns(projectId as string).filter(
                (column) => !!columnSettings[column.id]
              )}
              sortable
              sortSettings={sort}
              onSortSettingsChange={setSort}
            />
          </div>
        </Tabs.Content>
        <Tabs.Content value="gallery">
          <div className={styles.galleryContent}>
            <SessionGallery sessions={sessions} isLoading={isLoading} />
          </div>
        </Tabs.Content>
      </Tabs.Root>
      {sessions?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
