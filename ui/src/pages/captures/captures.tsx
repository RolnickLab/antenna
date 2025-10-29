import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useCaptures } from 'data-services/hooks/captures/useCaptures'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './capture-columns'
import { CaptureGallery } from './capture-gallery'
import { UploadImagesDialog } from './upload-images-dialog/upload-images-dialog'

export const Captures = () => {
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const { projectId } = useParams()
  const { selectedView, setSelectedView } = useSelectedView('table')
  const { filters } = useFilters()
  const { sort, setSort } = useSort({
    field: 'timestamp',
    order: 'desc',
  })
  const { pagination, setPage } = usePagination()
  const { captures, userPermissions, total, isLoading, isFetching, error } =
    useCaptures({
      projectId,
      sort,
      pagination,
      filters,
    })
  const showUpload = userPermissions?.includes(UserPermission.Create)

  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <div className="space-y-6">
        <FilterSection defaultOpen>
          <FilterControl field="deployment" />
          <FilterControl field="collections" />
        </FilterSection>
      </div>
      <div className="w-full overflow-hidden">
        <PageHeader
          title={translate(STRING.NAV_ITEM_CAPTURES)}
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
          <SortControl
            columns={columns(projectId as string)}
            setSort={setSort}
            sort={sort}
          />
          {showUpload ? (
            <UploadImagesDialog
              isOpen={isUploadOpen}
              setIsOpen={setIsUploadOpen}
            />
          ) : null}
        </PageHeader>
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
      </div>
      <PageFooter>
        {captures?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
    </div>
  )
}
