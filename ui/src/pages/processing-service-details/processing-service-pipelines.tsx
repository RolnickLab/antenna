import { Pipeline } from 'data-services/models/pipeline'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  Table,
  TableBackgroundTheme,
} from 'design-system/components/table/table/table'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Pipeline>[] = (
  projectId: string
) => [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: Pipeline) => (
      <Link
        to={APP_ROUTES.PIPELINE_DETAILS({
          projectId: projectId,
          pipelineId: item.id,
        })}
      >
        <BasicTableCell
          style={{ width: '240px', whiteSpace: 'normal' }}
          theme={CellTheme.Primary}
          value={item.name}
        />
      </Link>
    ),
  },
  {
    id: 'description',
    name: translate(STRING.FIELD_LABEL_DESCRIPTION),
    renderCell: (item: Pipeline) => (
      <BasicTableCell
        style={{ width: '320px', whiteSpace: 'normal' }}
        value={item.description}
      />
    ),
  },
]

export const ProcessingServicePipelines = ({
  processingService,
}: {
  processingService: ProcessingService
}) => {
  const { projectId } = useParams()

  return (
    <Table
      backgroundTheme={TableBackgroundTheme.White}
      items={processingService.pipelines}
      columns={columns(projectId as string)}
    />
  )
}
