import { useSessions } from 'data-services/hooks/useSessions'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import * as Tabs from 'design-system/components/tabs/tabs'
import React, { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useTableSettings } from 'utils/useTableSettings'
import { columns } from './session-columns'
import styles from './sessions.module.scss'

export const Sessions = () => {
  const [columnSettings, setColumnSettings] = useState<{
    [id: string]: boolean
  }>({
    snapshots: true,
    session: true,
    deployment: true,
    date: true,
    duration: true,
    occurrences: true,
    species: true,
  })
  const { sort, setSort, pagination, setPagination, fetchParams } =
    useTableSettings({ columns })
  const { sessions, total, isLoading } = useSessions(fetchParams)

  return (
    <>
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
              sortSettings={sort}
              onSortSettingsChange={setSort}
            />
          </div>
        </Tabs.Content>
        <Tabs.Content value="gallery">
          <div className={styles.galleryContent}></div>
        </Tabs.Content>
      </Tabs.Root>
      <PaginationBar
        page={pagination.page}
        perPage={pagination.perPage}
        total={total}
        onPrevClick={() =>
          setPagination({
            ...pagination,
            page: pagination.page - 1,
          })
        }
        onNextClick={() =>
          setPagination({
            ...pagination,
            page: pagination.page + 1,
          })
        }
      />
    </>
  )
}
