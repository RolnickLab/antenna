import { Deployment } from 'data-services/models/deployment'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
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
    id: 'device',
    name: translate(STRING.FIELD_LABEL_DEVICE),
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.device?.name} />
    ),
  },
  {
    id: 'research-site',
    name: translate(STRING.FIELD_LABEL_RESEARCH_SITE),
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.researchSite?.name} />
    ),
  },
  {
    id: 'status',
    name: 'Latest job status',
    renderCell: (item: Deployment) => {
      if (!item.currentJob) {
        return <></>
      }

      return (
        <StatusTableCell
          color={item.currentJob.status.color}
          details={item.currentJob.type.label}
          label={item.currentJob.status.label}
        />
      )
    },
  },
  {
    id: 'jobs',
    name: translate(STRING.FIELD_LABEL_JOBS),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.JOBS({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numJobs} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'captures',
    name: translate(STRING.FIELD_LABEL_CAPTURES),
    sortField: 'captures_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.CAPTURES({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numImages} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'sessions',
    name: translate(STRING.FIELD_LABEL_SESSIONS),
    sortField: 'events_count',
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
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'occurrences_count',
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
    id: 'taxa',
    name: translate(STRING.FIELD_LABEL_TAXA),
    sortField: 'taxa_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.TAXA({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numTaxa} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'first-date',
    name: translate(STRING.FIELD_LABEL_FIRST_DATE),
    sortField: 'first_capture_timestamp',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.firstDateLabel} />
    ),
  },
  {
    id: 'last-date',
    name: translate(STRING.FIELD_LABEL_LAST_DATE),
    sortField: 'last_capture_timestamp',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.lastDateLabel} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Deployment) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Deployment) => <BasicTableCell value={item.updatedAt} />,
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
