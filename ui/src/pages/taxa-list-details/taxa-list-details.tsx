import { TaxaListBadges } from 'components/taxa-list-badges/taxa-list-badges'
import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import { useTaxaListDetails } from 'data-services/hooks/taxa-lists/useTaxaListDetails'
import {
  Dialog,
  PageFooter,
  PageHeader,
  PaginationBar,
  SortControl,
  Table,
} from 'nova-ui-kit'
import { SpeciesDetails, TABS } from 'pages/species-details/species-details'
import { useContext, useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { useSelectedView } from 'utils/useSelectedView'
import { useSort } from 'utils/useSort'
import { useUser } from 'utils/user/userContext'
import { AddTaxaListTaxonPopover } from './add-taxa-list-taxon/add-taxa-list-taxon-popover'
import { CopyTaxaListDialog } from './copy-taxa-list/copy-taxa-list-dialog'
import { columns } from './taxa-list-details-columns'

export const TaxaListDetails = () => {
  const { projectId, id, taxonId } = useParams()
  const { user } = useUser()
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
      { field: 'include_descendants', value: 'false' },
      { field: 'taxa_list_id', value: id },
    ],
  })

  useEffect(() => {
    setDetailBreadcrumb(
      taxaList
        ? { title: taxaList.name }
        : { title: `${translate(STRING.LOADING_DATA)}...` }
    )

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [taxaList, setDetailBreadcrumb])
  const tableColumns = columns({
    // A managed list's membership mirrors a classifier's category map and
    // can't be edited directly: it must be copied first. See #1420.
    canUpdate: taxaList?.canUpdate && !taxaList?.isManaged,
    projectId: projectId as string,
    taxaListId: id as string,
  })

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
        {taxaList ? (
          <TaxaListBadges projectId={projectId as string} taxaList={taxaList} />
        ) : null}
        {taxaList?.canUpdate && !taxaList.isManaged ? (
          <AddTaxaListTaxonPopover taxaListId={id as string} />
        ) : null}
        {taxaList && user.loggedIn ? (
          <CopyTaxaListDialog taxaList={taxaList} />
        ) : null}
        <SortControl columns={tableColumns} setSort={setSort} sort={sort} />
      </PageHeader>
      {taxaList?.isManaged ? (
        <div className="mb-4 body-small text-muted-foreground">
          <p>{translate(STRING.MESSAGE_TAXA_LIST_MANAGED)}</p>
          <p>
            {translate(STRING.ALGORITHMS)}:{' '}
            {taxaList.algorithms.map((algorithm, index) => (
              <span key={algorithm.id}>
                {index > 0 ? ', ' : null}
                <Link
                  className="underline"
                  to={APP_ROUTES.ALGORITHM_DETAILS({
                    projectId: projectId as string,
                    algorithmId: `${algorithm.id}`,
                  })}
                >
                  {algorithm.name}
                </Link>
              </span>
            ))}
          </p>
        </div>
      ) : null}
      <Table
        columns={tableColumns}
        error={error}
        isLoading={isLoading}
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
      {taxonId ? (
        <SpeciesDetailsDialog taxaListId={id as string} taxonId={taxonId} />
      ) : null}
    </>
  )
}

const SpeciesDetailsDialog = ({
  taxaListId,
  taxonId,
}: {
  taxaListId: string
  taxonId: string
}) => {
  const navigate = useNavigate()
  const { selectedView, setSelectedView } = useSelectedView(TABS.FIELDS, 'tab')
  const { projectId } = useParams()
  const { species, isLoading, error } = useSpeciesDetails(taxonId, projectId)

  return (
    <Dialog.Root
      open={!!taxonId}
      onOpenChange={(open) => {
        if (!open) {
          setSelectedView(undefined)
        }

        navigate(
          getAppRoute({
            to: APP_ROUTES.TAXA_LIST_DETAILS({
              projectId: projectId as string,
              taxaListId,
            }),
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
