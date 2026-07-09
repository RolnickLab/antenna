import { DefaultFiltersControl } from 'components/filtering/default-filter-control'
import { FilterControl } from 'components/filtering/filter-control'
import { FilterSection } from 'components/filtering/filter-section'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import { useTaxaLists } from 'data-services/hooks/taxa-lists/useTaxaLists'
import { useTags } from 'data-services/hooks/taxa-tags/useTags'
import { Grid2x2Icon, TableIcon } from 'lucide-react'
import {
  ColumnSettings,
  Dialog,
  PageFooter,
  PageHeader,
  PaginationBar,
  SortControl,
  Table,
  ToggleGroup,
} from 'nova-ui-kit'
import { OccurrenceDetailsDialog } from 'pages/occurrences/occurrence-details-dialog'
import { TABS as OCCURRENCE_TABS } from 'pages/occurrence-details/occurrence-details'
import { SpeciesDetails, TABS } from 'pages/species-details/species-details'
import { useContext, useEffect, useMemo, useRef } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
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
  const [searchParams, setSearchParams] = useSearchParams()
  // Occurrence to verify in a modal over the taxa list. Keyed off a search
  // param (not the :id path segment, which already means taxon detail).
  const verifyOccurrenceId = searchParams.get('verifyOccurrence') ?? undefined
  const { project } = useProjectDetails(projectId as string, true)
  const { columnSettings, setColumnSettings } = useColumnSettings('species', {
    'cover-image': true,
    example: true,
    name: true,
    rank: false,
    'last-seen': true,
    occurrences: true,
    verified: true,
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
  // Ordered example occurrences, one per taxon row that has one, so the modal's
  // prev/next steps to the next taxon's example (rows without an example are skipped).
  const exampleNavItems = useMemo(
    () =>
      (species ?? []).flatMap((item) =>
        item.verificationExample
          ? [{ id: String(item.verificationExample.id) }]
          : []
      ),
    [species]
  )
  // Remember where the open example sits in the list so the sweep can continue if it
  // drops out. After verifying, that row's example rolls to a different occurrence (or,
  // under ?verified=false, the row leaves the list), so the open ?verifyOccurrence id is
  // no longer in exampleNavItems. Advance to whatever example now occupies that position
  // instead of dead-ending with both nav buttons disabled.
  const verifyIndexRef = useRef(-1)
  useEffect(() => {
    if (!verifyOccurrenceId || exampleNavItems.length === 0) {
      return
    }
    const index = exampleNavItems.findIndex(
      (item) => item.id === verifyOccurrenceId
    )
    if (index >= 0) {
      verifyIndexRef.current = index
      return
    }
    const nextId =
      exampleNavItems[
        Math.min(verifyIndexRef.current, exampleNavItems.length - 1)
      ]?.id
    if (nextId) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('verifyOccurrence', nextId)
          return next
        },
        { replace: true }
      )
    }
  }, [exampleNavItems, verifyOccurrenceId, setSearchParams])
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
          <FilterControl field="verified" />
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
                  Icon: TableIcon,
                },
                {
                  value: 'gallery',
                  label: translate(STRING.TAB_ITEM_GALLERY),
                  Icon: Grid2x2Icon,
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
              isLoading={!id && !verifyOccurrenceId && isLoading}
              items={species}
              onSortSettingsChange={setSort}
              rowClassName={(item) =>
                item.numVerified > 0 ? 'opacity-50' : undefined
              }
              sortable
              sortSettings={sort}
            />
          )}
          {selectedView === 'gallery' && (
            <SpeciesGallery
              error={error}
              isLoading={!id && !verifyOccurrenceId && isLoading}
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
      {verifyOccurrenceId ? (
        <OccurrenceDetailsDialog
          id={verifyOccurrenceId}
          occurrences={exampleNavItems}
          defaultTab={OCCURRENCE_TABS.IDENTIFICATION}
          onNavigate={(occurrenceId) => {
            const nextParams = new URLSearchParams(searchParams)
            nextParams.set('verifyOccurrence', occurrenceId)
            setSearchParams(nextParams)
          }}
          onClose={() => {
            const nextParams = new URLSearchParams(searchParams)
            nextParams.delete('verifyOccurrence')
            setSearchParams(nextParams)
          }}
        />
      ) : null}
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
