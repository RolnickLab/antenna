import { BatchData } from 'data-services/types'
import { useBatchData } from 'data-services/useBatchId'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { Table } from 'design-system/components/table/table/table'
import { TableColumn, TextAlign } from 'design-system/components/table/types'
import React from 'react'
import { STRING, translate } from 'utils/language'
import styles from './batch-id-table.module.scss'

const columns: TableColumn<BatchData>[] = [
  {
    id: 'description',
    name: translate(STRING.TABLE_COLUMN_DESCRIPTION),
    visuallyHidden: true,
    renderCell: (item: BatchData) => (
      <BasicTableCell value={item.description} />
    ),
  },
  {
    id: 'unprocessed',
    name: translate(STRING.TABLE_COLUMN_UNPROCESSED),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: BatchData) => (
      <BasicTableCell value={item.unprocessed} />
    ),
  },
  {
    id: 'queued',
    name: translate(STRING.TABLE_COLUMN_QUEUED),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: BatchData) => <BasicTableCell value={item.queued} />,
  },
  {
    id: 'complete',
    name: translate(STRING.TABLE_COLUMN_COMPLETE),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: BatchData) => <BasicTableCell value={item.complete} />,
  },
  {
    id: 'status',
    name: translate(STRING.TABLE_COLUMN_STATUS),
    renderCell: (item: BatchData) => (
      <BasicTableCell value={item.statusLabel} />
    ),
  },
  {
    id: 'actions',
    name: translate(STRING.TABLE_COLUMN_ACTIONS),
    visuallyHidden: true,
    renderCell: (item) => {
      const showQueueUnprocessedButton = item.unprocessed > 0
      const showDequeueButton = item.queued > 0

      return (
        <BasicTableCell>
          <div className={styles.actionCellContent}>
            {showQueueUnprocessedButton && (
              <Button
                label={translate(STRING.QUEUE_ALL)}
                theme={ButtonTheme.Success}
                onClick={() => console.log('')}
              />
            )}
            {showDequeueButton && (
              <Button
                label={translate(STRING.DEQUE_ALL)}
                onClick={() => console.log('')}
              />
            )}
          </div>
        </BasicTableCell>
      )
    },
  },
]

export const BatchIdTable = () => {
  const batchData = useBatchData()

  return <Table items={batchData} columns={columns}></Table>
}
