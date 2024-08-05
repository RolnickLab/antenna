import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { useOccurrences } from 'data-services/hooks/occurrences/useOccurrences'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
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
    deployment: true,
    duration: false,
    detections: true,
    score: true,
    ['created-at']: true,
  })
  const { sort, setSort } = useSort({
    field: 'created_at',
    order: 'desc',
  })
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
    return <Error error={error} />
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_OCCURRENCES)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        showAppliedFilters
        tooltip={translate(STRING.TOOLTIP_OCCURRENCE)}
      >
        <ToggleGroup
          items={[
            {
              value: 'table',
              label: translate(STRING.TAB_ITEM_TABLE),
              icon: IconType.TableView,
            },
            {
              value: 'gallery',
              label: translate(STRING.TAB_ITEM_GALLERY),
              icon: IconType.GalleryView,
            },
          ]}
          value={selectedView}
          onValueChange={setSelectedView}
        />
        <ColumnSettings
          columns={columns(projectId as string)}
          columnSettings={columnSettings}
          onColumnSettingsChange={setColumnSettings}
        />
      </PageHeader>
      {selectedView === 'table' && (
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
      )}
      {selectedView === 'gallery' && (
        <div className={styles.galleryContent}>
          <OccurrenceGallery occurrences={occurrences} isLoading={isLoading} />
        </div>
      )}
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
  const { occurrence, isLoading, error } = useOccurrenceDetails(id)

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
        error={error}
      >
        {occurrence ? <OccurrenceDetails occurrence={occurrence} /> : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
