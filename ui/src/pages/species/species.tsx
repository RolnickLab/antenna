import { FetchInfo } from 'components/fetch-info/fetch-info'
import { FilterSettings } from 'components/filter-settings/filter-settings'
import { useSpecies } from 'data-services/hooks/species/useSpecies'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Table } from 'design-system/components/table/table/table'
import * as Tabs from 'design-system/components/tabs/tabs'
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
  const { sort, setSort } = useSort()
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
      <div className={styles.infoWrapper}>
        {isFetching && <FetchInfo isLoading={isLoading} />}
        <FilterSettings />
      </div>
      <Tabs.Root value={selectedView} onValueChange={setSelectedView}>
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
              items={species}
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
            <SpeciesGallery species={species} isLoading={isLoading} />
          </div>
        </Tabs.Content>
      </Tabs.Root>
      {species?.length ? (
        <PaginationBar
          pagination={pagination}
          total={total}
          setPage={setPage}
        />
      ) : null}

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
