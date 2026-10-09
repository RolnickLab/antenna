import { Algorithm, AlgorithmEvaluation } from 'data-services/models/algorithm'
import {
  BasicTableCell,
  Table,
  TableBackgroundTheme,
  TableColumn,
  TextAlign,
} from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

const ACCURACY_DECIMALS = 2

const accuracyLabel = (accuracy?: number) =>
  accuracy !== undefined
    ? accuracy.toFixed(ACCURACY_DECIMALS)
    : translate(STRING.VALUE_NOT_AVAILABLE)

export const columns: TableColumn<AlgorithmEvaluation>[] = [
  {
    id: 'occurrence-set',
    name: translate(STRING.FIELD_LABEL_EVALUATION_SET),
    renderCell: (item: AlgorithmEvaluation) => (
      <BasicTableCell
        style={{ width: '150px', whiteSpace: 'normal' }}
        value={item.occurrenceSetName}
      />
    ),
  },
  {
    id: 'accuracy',
    name: translate(STRING.FIELD_LABEL_ACCURACY),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: AlgorithmEvaluation) => (
      <BasicTableCell value={accuracyLabel(item.accuracy)} />
    ),
  },
  {
    id: 'accuracy-by-species',
    name: translate(STRING.FIELD_LABEL_ACCURACY_BY_SPECIES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: AlgorithmEvaluation) => (
      <BasicTableCell value={accuracyLabel(item.accuracyBySpecies)} />
    ),
  },
  {
    id: 'occurrences-scored',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES_SCORED),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: AlgorithmEvaluation) => (
      <BasicTableCell value={item.occurrencesScored} />
    ),
  },
]

export const AlgorithmEvaluations = ({
  algorithm,
}: {
  algorithm: Algorithm
}) => (
  <Table
    backgroundTheme={TableBackgroundTheme.White}
    items={algorithm.evaluations}
    columns={columns}
  />
)
