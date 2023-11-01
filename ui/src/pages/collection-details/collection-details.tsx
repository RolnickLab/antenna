import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useCaptures } from 'data-services/hooks/captures/useCaptures'
import { useCollectionDetails } from 'data-services/hooks/collections/useCollectionDetails'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { useContext, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { columns } from './capture-columns'
import { CaptureGallery } from './capture-gallery'
import styles from './collection-details.module.scss'

export const CollectionDetails = () => {
  const { projectId, id } = useParams()

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
    return <Error />
  }

  return (
    <>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
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
            <Table
              items={captures}
              isLoading={isLoading}
              columns={columns(projectId as string)}
              sortable
              sortSettings={sort}
              onSortSettingsChange={setSort}
            />
          </div>
        </Tabs.Content>
        <Tabs.Content value="gallery">
          <div className={styles.galleryContent}>
            <CaptureGallery captures={captures} isLoading={isLoading} />
          </div>
        </Tabs.Content>
      </Tabs.Root>

      {captures?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}
    </>
  )
}
