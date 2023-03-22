import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import React, { useState } from 'react'
import { columns, SessionsTable } from './sessions-table/sessions-table'
import * as Tabs from 'design-system/components/tabs/tabs'
import styles from './sessions.module.scss'
import { STRING, translate } from 'utils/language'
import { IconType } from 'design-system/components/icon/icon'

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
          <SessionsTable columnSettings={columnSettings} />
        </div>
      </Tabs.Content>
      <Tabs.Content value="gallery">
        <div className={styles.galleryContent}>
          <div className={styles.sidebar}></div>
          <div className={styles.gallery}></div>
        </div>
      </Tabs.Content>
    </Tabs.Root>
  )
}
