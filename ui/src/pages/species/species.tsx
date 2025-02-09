import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { SpeciesDetails } from 'pages/species-details/species-details'
import { useContext, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './species-columns'
import { SpeciesGallery } from './species-gallery'

export const Species = () => {
  const { projectId, id } = useParams()
  const { sort, setSort } = useSort({ field: 'name', order: 'asc' })
  const { pagination, setPage } = usePagination()
  const { filters } = useFilters()
  const { species, total, isLoading, isFetching, error } = useSpecies({
    projectId,
    sort,
    pagination,
    filters,
  })
  const { selectedView, setSelectedView } = useSelectedView('table')

  return (
    <>
      <div className="flex flex-col gap-6 md:flex-row">
        <FilterSection defaultOpen>
          <FilterControl field="event" readonly />
          <FilterControl field="deployment" />
          <FilterControl field="taxon" />
        </FilterSection>
        <div className="w-full overflow-hidden">
          <PageHeader
            isFetching={isFetching}
            isLoading={isLoading}
            subTitle={translate(STRING.RESULTS, {
              total,
            })}
            title={translate(STRING.NAV_ITEM_TAXA)}
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
          {selectedView === 'table' && (
            <Table
              columns={columns(projectId as string)}
              error={error}
              isLoading={!id && isLoading}
              items={species}
              onSortSettingsChange={setSort}
              sortable
              sortSettings={sort}
            />
          )}
          {selectedView === 'gallery' && (
            <SpeciesGallery
              error={error}
              isLoading={!id && isLoading}
              species={species}
            />
          )}
        </div>
      </div>
      <PageFooter>
        {species?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
      {id ? <SpeciesDetailsDialog id={id} /> : null}
    </>
  )
}

const SpeciesDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { species, isLoading, error } = useSpeciesDetails(id, projectId)

  useEffect(() => {
    setDetailBreadcrumb(species ? { title: species.name } : undefined)

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [species])

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.TAXA({ projectId: projectId as string }),
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
        {species ? <SpeciesDetails species={species} /> : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
