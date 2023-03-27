import { useSessions } from 'data-services/hooks/useSessions'
import { IconType } from 'design-system/components/icon/icon'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import * as Tabs from 'design-system/components/tabs/tabs'
import React, { useMemo, useState } from 'react'
import { getFetchSettings } from 'utils/getFetchSettings'
import { STRING, translate } from 'utils/language'
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
  const [sortSettings, setSortSettings] = useState<TableSortSettings>()
  const fetchSettings = useMemo(
    () => getFetchSettings({ columns, sortSettings }),
    [sortSettings]
  )
  const { sessions, isLoading } = useSessions(fetchSettings)

  return (
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
            sortSettings={sortSettings}
            onSortSettingsChange={setSortSettings}
          />
        </div>
      </Tabs.Content>
      <Tabs.Content value="gallery">
        <div className={styles.galleryContent}></div>
      </Tabs.Content>
    </Tabs.Root>
  )
}
