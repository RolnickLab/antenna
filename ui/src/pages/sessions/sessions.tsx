import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useSessions } from 'data-services/hooks/useSessions'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { columns } from './session-columns'
import styles from './sessions.module.scss'

export const Sessions = () => {
  const [columnSettings, setColumnSettings] = useState<{
    [id: string]: boolean
  }>({
    snapshots: true,
    session: true,
    images: true,
    date: true,
    duration: true,
    occurrences: true,
    species: true,
  })
  const [sort, setSort] = useState<TableSortSettings>()
  const { pagination, setPrevPage, setNextPage } = usePagination()
  const { sessions, total, isLoading, isFetching, error } = useSessions({
    sort,
    pagination,
  })

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <Tabs.Root defaultValue="table">
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
                columns={columns}
                columnSettings={columnSettings}
                onColumnSettingsChange={setColumnSettings}
              />
            </div>
            <Table
              items={sessions}
              isLoading={isLoading}
              columns={columns.filter((column) => !!columnSettings[column.id])}
              sortable
              sortSettings={sort}
              onSortSettingsChange={setSort}
            />
          </div>
        </Tabs.Content>
        <Tabs.Content value="gallery">
          <div className={styles.galleryContent}>
            <UnderConstruction message="Gallery is under construction!" />
          </div>
        </Tabs.Content>
      </Tabs.Root>
      {sessions?.length ? (
        <PaginationBar
          page={pagination.page}
          perPage={pagination.perPage}
          total={total}
          onPrevClick={setPrevPage}
          onNextClick={setNextPage}
        />
      ) : null}
    </>
  )
}
