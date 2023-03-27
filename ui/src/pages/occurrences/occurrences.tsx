import { useOccurrences } from 'data-services/hooks/useOccurrences'
import { Card } from 'design-system/components/card/card'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import * as Tabs from 'design-system/components/tabs/tabs'
import React from 'react'
import { STRING, translate } from 'utils/language'
import { useTableSettings } from 'utils/useTableSettings'
import { columns } from './occurrence-columns'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  const { sort, setSort, pagination, setPagination, fetchParams } =
    useTableSettings({
      columns,
    })
  const { occurrences, total, isLoading } = useOccurrences(fetchParams)

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
          <div className={styles.occurrencesContent}>
            <Table
              items={occurrences}
              isLoading={isLoading}
              columns={columns}
              sortSettings={sort}
              onSortSettingsChange={setSort}
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
