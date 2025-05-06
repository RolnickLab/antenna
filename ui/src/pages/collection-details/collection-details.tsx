import { useCaptures } from 'data-services/hooks/captures/useCaptures'
import { useCollectionDetails } from 'data-services/hooks/collections/useCollectionDetails'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { TableSortSettings } from 'design-system/components/table/types'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { columns } from './capture-columns'
import { CaptureGallery } from './capture-gallery'

export const CollectionDetails = () => {
  const { projectId, id } = useParams()
  const { selectedView, setSelectedView } = useSelectedView('table')

  // Collection details
  const { collection } = useCollectionDetails(id as string)

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
          columns={columns(projectId as string)}
          error={error}
          isLoading={isLoading}
          items={captures}
          onSortSettingsChange={setSort}
          sortable
          sortSettings={sort}
        />
      )}
      {selectedView === 'gallery' && (
        <CaptureGallery
          captures={captures}
          error={error}
          isLoading={isLoading}
        />
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
