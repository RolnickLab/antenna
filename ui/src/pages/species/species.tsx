import { DefaultFiltersControl } from 'components/filtering/default-filter-control'
import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { useTags } from 'data-services/hooks/taxa-tags/useTags'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { ColumnSettings } from 'design-system/components/table/column-settings/column-settings'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { SpeciesDetails, TABS } from 'pages/species-details/species-details'
import { useContext, useEffect, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useColumnSettings } from 'utils/useColumnSettings'
import { useFilters } from 'utils/useFilters'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { columns } from './species-columns'
import { SpeciesGallery } from './species-gallery'

export const Species = () => {
  const { projectId, id } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const { columnSettings, setColumnSettings } = useColumnSettings('species', {
    'cover-image': true,
    name: true,
    rank: false,
    'last-seen': true,
    occurrences: true,
    'best-determination-score': true,
    'created-at': false,
    'updated-at': false,
  })
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
  const { taxaLists = [] } = useTaxaLists({ projectId: projectId as string })
  const { tags = [] } = useTags({ projectId: projectId as string })
  const pageTitle = useMemo(() => {
    const taxaListFilter = filters.find(
      (filter) => filter.field === 'taxa_list_id'
    )
    const activeTaxaList = taxaListFilter
      ? taxaLists.find((taxaList) => taxaList.id === taxaListFilter.value)
      : undefined

    return activeTaxaList
      ? activeTaxaList.name
      : translate(STRING.NAV_ITEM_TAXA)
  }, [filters, taxaLists])

  return (
    <>
      <div className="flex flex-col gap-6 md:flex-row">
        <FilterSection defaultOpen>
          <FilterControl field="event" readonly />
          <FilterControl field="deployment" />
          <FilterControl field="taxon" />
          {taxaLists.length > 0 && (
            <>
              <FilterControl data={taxaLists} field="taxa_list_id" />
              <FilterControl data={taxaLists} field="not_taxa_list_id" />
            </>
          )}
          <FilterControl field="include_unobserved" />
          {project?.featureFlags.tags ? (
            <>
              <FilterControl data={tags} field="tag_id" />
              <FilterControl data={tags} field="not_tag_id" />
            </>
          ) : null}
          <DefaultFiltersControl field="apply_defaults" />
        </FilterSection>
        <div className="w-full overflow-hidden">
          <PageHeader
            isFetching={isFetching}
            isLoading={isLoading}
            subTitle={translate(STRING.RESULTS, {
              total,
            })}
            title={pageTitle}
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
              columns={columns({ projectId: projectId as string })}
              setSort={setSort}
              sort={sort}
            />
            <ColumnSettings
              columns={columns({ projectId: projectId as string })}
              columnSettings={columnSettings}
              onColumnSettingsChange={setColumnSettings}
            />
          </PageHeader>
          {selectedView === 'table' && (
            <Table
              columns={columns({
                projectId: projectId as string,
                featureFlags: project?.featureFlags,
              }).filter((column) => !!columnSettings[column.id])}
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
  const { selectedView, setSelectedView } = useSelectedView(TABS.FIELDS, 'tab')
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
      onOpenChange={(open) => {
        if (!open) {
          setSelectedView(undefined)
        }

        navigate(
          getAppRoute({
            to: APP_ROUTES.TAXA({ projectId: projectId as string }),
            keepSearchParams: true,
          })
        )
      }}
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        error={error}
        isLoading={isLoading}
        onOpenAutoFocus={(e) => {
          /* Prevent tooltip auto focus */
          e.preventDefault()
          ;(e.currentTarget as HTMLElement).focus()
        }}
      >
        {species ? (
          <SpeciesDetails
            species={species}
            selectedTab={selectedView}
            setSelectedTab={setSelectedView}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
