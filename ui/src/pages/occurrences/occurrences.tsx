import { FilterSettings } from 'components/filter-settings/filter-settings'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { useOccurrences } from 'data-services/hooks/occurrences/useOccurrences'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { OccurrenceDetails } from 'pages/occurrence-details/occurrence-details'
import { useContext, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './occurrence-columns'
import { OccurrenceGallery } from './occurrence-gallery'
import styles from './occurrences.module.scss'

export const Occurrences = () => {
  const { projectId, id } = useParams()
  const [columnSettings, setColumnSettings] = useState<{
    [id: string]: boolean
  }>({
    snapshots: true,
    id: true,
    date: true,
    time: true,
    deployment: true,
    duration: false,
    detections: true,
    score: true,
  })
  const { sort, setSort } = useSort()
  const { pagination, setPage } = usePagination()
  const { filters } = useFilters()
  const { occurrences, total, isLoading, isFetching, error } = useOccurrences({
    projectId,
    pagination,
    sort,
    filters,
  })
  const { selectedView, setSelectedView } = useSelectedView('table')

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_OCCURRENCES)}
        subTitle={`${total} results`}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        <FilterSettings />
        <ColumnSettings
          columns={columns(projectId as string)}
          columnSettings={columnSettings}
          onColumnSettingsChange={setColumnSettings}
        />
      </PageHeader>
      <Tabs.Root value={selectedView} onValueChange={setSelectedView}>
        {/* <Tabs.List>
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
        </Tabs.List> */}
        <Tabs.Content value="table">
          <Table
            items={occurrences}
            isLoading={isLoading}
            columns={columns(projectId as string).filter(
              (column) => !!columnSettings[column.id]
            )}
            sortable
            sortSettings={sort}
            onSortSettingsChange={setSort}
          />
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
      <PageFooter>
        {occurrences?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
      {!isLoading && id ? <OccurrenceDetailsDialog id={id} /> : null}
    </>
  )
}

const OccurrenceDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { occurrence, isLoading } = useOccurrenceDetails(id)

  useEffect(() => {
    setDetailBreadcrumb(
      occurrence ? { title: occurrence.displayName } : undefined
    )

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [occurrence])

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {occurrence ? <OccurrenceDetails occurrence={occurrence} /> : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
