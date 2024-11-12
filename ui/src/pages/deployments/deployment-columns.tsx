import { Deployment } from 'data-services/models/deployment'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { DeleteDeploymentDialog } from 'pages/deployment-details/delete-deployment-dialog'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './deployments.module.scss'

export const columns: (projectId: string) => TableColumn<Deployment>[] = (
  projectId: string
) => [
  {
    id: 'snapshot',
    name: translate(STRING.FIELD_LABEL_IMAGE),
    renderCell: (item: Deployment) => {
      const detailsRoute = getAppRoute({
        to: APP_ROUTES.DEPLOYMENT_DETAILS({ projectId, deploymentId: item.id }),
        keepSearchParams: true,
      })

      return (
        <ImageTableCell
          images={item.image ? [{ src: item.image }] : []}
          theme={ImageCellTheme.Light}
          to={detailsRoute}
        />
      )
    },
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    sortField: 'name',
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId,
            deploymentId: item.id,
          }),
          keepSearchParams: true,
        })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'sessions',
    name: translate(STRING.FIELD_LABEL_SESSIONS),
    sortField: 'numEvents',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SESSIONS({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numEvents} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'captures',
    name: translate(STRING.FIELD_LABEL_CAPTURES),
    sortField: 'numImages',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'numOccurrences',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'species',
    name: translate(STRING.FIELD_LABEL_SPECIES),
    sortField: 'numSpecies',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SPECIES({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numSpecies} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'firstDate',
    name: translate(STRING.FIELD_LABEL_FIRST_DATE),
    sortField: 'firstDate',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.firstDateLabel} />
    ),
  },
  {
    id: 'lastDate',
    name: translate(STRING.FIELD_LABEL_LAST_DATE),
    sortField: 'lastDate',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.lastDateLabel} />
    ),
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Deployment) => (
      <div className={styles.deploymentActions}>
        {item.canDelete && <DeleteDeploymentDialog id={item.id} />}
      </div>
    ),
  },
]
