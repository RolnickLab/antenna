import { useOccurrences } from 'data-services/hooks/useOccurrences'
import { FetchSettings } from 'data-services/types'
import { Card } from 'design-system/components/card/card'
import { IconType } from 'design-system/components/icon/icon'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import * as Tabs from 'design-system/components/tabs/tabs'
import React, { useMemo, useState } from 'react'
import { getFetchSettings } from 'utils/getFetchSettings'
import { STRING, translate } from 'utils/language'
import { columns } from './occurrence-columns'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  const [sortSettings, setSortSettings] = useState<TableSortSettings>()
  const fetchSettings = useMemo(
    () => getFetchSettings({ columns, sortSettings }),
    [sortSettings]
  )
  const { occurrences, isLoading } = useOccurrences(fetchSettings)

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
        <div className={styles.occurrencesContent}>
          <Table
            items={occurrences}
            isLoading={isLoading}
            columns={columns}
            sortSettings={sortSettings}
            onSortSettingsChange={setSortSettings}
          />
        </div>
      </Tabs.Content>
      <Tabs.Content value="gallery">
        <div className={styles.galleryContent}>
          <div className={styles.sidebar}></div>
          <div className={styles.gallery}>
            {occurrences.map((occurrence) => (
              <Card
                key={occurrence.id}
                title={occurrence.categoryLabel}
                subTitle={occurrence.familyLabel}
                image={occurrence.images[0]}
                maxWidth="262px"
              />
            ))}
          </div>
        </div>
      </Tabs.Content>
    </Tabs.Root>
  )
}
