import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import { useTaxaListDetails } from 'data-services/hooks/taxa-lists/useTaxaListDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { SortControl } from 'design-system/components/sort-control'
import { Table } from 'design-system/components/table/table/table'
import { SpeciesDetails, TABS } from 'pages/species-details/species-details'
import { useContext, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { AddTaxaListTaxonPopover } from './add-taxa-list-taxon/add-taxa-list-taxon-popover'
import { columns } from './taxa-list-details-columns'

export const TaxaListDetails = () => {
  const { projectId, id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { sort, setSort } = useSort({ field: 'name', order: 'asc' })
  const { pagination, setPage } = usePagination()
  const { taxaList } = useTaxaListDetails(id as string, projectId as string)
  const { species, total, isLoading, isFetching, error } = useSpecies({
    projectId,
    sort,
    pagination,
    filters: [
      { field: 'include_unobserved', value: 'true' },
      { field: 'taxa_list_id', value: id },
    ],
  })

  useEffect(() => {
    setDetailBreadcrumb(
      taxaList ? { title: taxaList.name } : { title: 'Loading...' }
    )

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [taxaList])

  return (
    <>
      <PageHeader
        isFetching={isFetching}
        isLoading={isLoading}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        title={taxaList?.name ?? `${translate(STRING.LOADING_DATA)}...`}
      >
        <SortControl
          columns={columns({ projectId: projectId as string })}
          setSort={setSort}
          sort={sort}
        />
        <AddTaxaListTaxonPopover taxaListId={id as string} />
      </PageHeader>
      <Table
        columns={columns({
          projectId: projectId as string,
        })}
        error={error}
        isLoading={!id && isLoading}
        items={species}
        onSortSettingsChange={setSort}
        sortable
        sortSettings={sort}
      />
      <PageFooter>
        {species?.length ? (
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
        isLoading={isLoading}
        error={error}
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
