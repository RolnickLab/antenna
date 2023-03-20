import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import React, { useState } from 'react'
import { columns, SessionsTable } from './sessions-table/sessions-table'
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

  return (
    <>
      <div className={styles.settingsWrapper}>
        <ColumnSettings
          columns={columns}
          columnSettings={columnSettings}
          onColumnSettingsChange={setColumnSettings}
        />
      </div>
      <SessionsTable columnSettings={columnSettings} />
    </>
  )
}
