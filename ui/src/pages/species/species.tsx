import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import { ToggleGroup } from 'design-system/components/toggle-group/toggle-group'
import { Error } from 'pages/error/error'
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
import styles from './species.module.scss'

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

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_SPECIES)}
        subTitle={translate(STRING.RESULTS, {
          total,
        })}
        isLoading={isLoading}
        isFetching={isFetching}
        showAppliedFilters
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
          items={species}
          isLoading={isLoading}
          columns={columns(projectId as string)}
          sortable
          sortSettings={sort}
          onSortSettingsChange={setSort}
        />
      )}
      {selectedView === 'gallery' && (
        <div className={styles.galleryContent}>
          <SpeciesGallery species={species} isLoading={isLoading} />
        </div>
      )}
      <PageFooter>
        {species?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
      {!isLoading && id ? <SpeciesDetailsDialog id={id} /> : null}
    </>
  )
}

const SpeciesDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { species, isLoading } = useSpeciesDetails(id, projectId)

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
            to: APP_ROUTES.SPECIES({ projectId: projectId as string }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {species ? <SpeciesDetails species={species} /> : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
