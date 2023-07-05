import { FetchInfo } from 'components/fetch-info/fetch-info'
import { FilterSettings } from 'components/filter-settings/filter-settings'
import { useOccurrences } from 'data-services/hooks/useOccurrences'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { OccurrenceDetails } from 'pages/occurrence-details/occurrence-details'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { columns } from './occurrence-columns'
import { OccurrenceGallery } from './occurrence-gallery'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const [columnSettings, setColumnSettings] = useState<{
    [id: string]: boolean
  }>({
    snapshots: true,
    id: true,
    deployment: true,
    session: true,
    duration: true,
    detections: true,
  })
  const [sort, setSort] = useState<TableSortSettings>()
  const { pagination, setPrevPage, setNextPage } = usePagination()
  const { filters } = useFilters()
  const { occurrences, total, isLoading, isFetching, error } = useOccurrences({
    pagination,
    sort,
    filters,
  })

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      <div className={styles.infoWrapper}>
        {isFetching && <FetchInfo isLoading={isLoading} />}
        <FilterSettings />
      </div>
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
              items={occurrences}
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
            <OccurrenceGallery
              occurrences={occurrences}
              isLoading={isLoading}
            />
          </div>
        </Tabs.Content>
      </Tabs.Root>
      {occurrences?.length ? (
        <PaginationBar
          page={pagination.page}
          perPage={pagination.perPage}
          total={total}
          onPrevClick={setPrevPage}
          onNextClick={setNextPage}
        />
      ) : null}

      <Dialog.Root open={!!id} onOpenChange={() => navigate('/occurrences')}>
        <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
          {id ? <OccurrenceDetails id={id} /> : null}
        </Dialog.Content>
      </Dialog.Root>
    </>
  )
}
