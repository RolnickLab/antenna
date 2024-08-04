import { useCaptures } from 'data-services/hooks/captures/useCaptures'
import { useCollectionDetails } from 'data-services/hooks/collections/useCollectionDetails'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { Error } from 'pages/error/error'
import { useContext, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { columns } from './capture-columns'
import { CaptureGallery } from './capture-gallery'
import styles from './collection-details.module.scss'

export const CollectionDetails = () => {
  const { projectId, id } = useParams()
  const { selectedView, setSelectedView } = useSelectedView('table')

  // Collection details
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { collection } = useCollectionDetails(id as string)

  useEffect(() => {
    setDetailBreadcrumb(collection ? { title: collection.name } : undefined)

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [collection])

  // Collection captures
  const [sort, setSort] = useState<TableSortSettings>()
  const { pagination, setPage } = usePagination()
  const { captures, total, isLoading, isFetching, error } = useCaptures({
    projectId,
    pagination,
    sort,
    filters: [
      {
        field: 'collections',
        value: id as string,
      },
    ],
  })

  if (!isLoading && error) {
    return <Error error={error} />
  }

  return (
    <>
      {collection && (
        <PageHeader
          title={collection.name}
          subTitle={translate(STRING.RESULTS, {
            total,
          })}
          isLoading={isLoading}
          isFetching={isFetching}
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
        </PageHeader>
      )}
      {selectedView === 'table' && (
        <Table
          items={captures}
          isLoading={isLoading}
          columns={columns(projectId as string)}
          sortable
          sortSettings={sort}
          onSortSettingsChange={setSort}
        />
      )}
      {selectedView === 'gallery' && (
        <div className={styles.galleryContent}>
          <CaptureGallery captures={captures} isLoading={isLoading} />
        </div>
      )}
      <PageFooter>
        {captures?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
    </>
  )
}
