import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { Table } from 'design-system/components/table/table/table'
import { CellTheme, TextAlign } from 'design-system/components/table/types'
import React from 'react'
import styles from './deployments.module.scss'
import { deployments } from './mockDeployments'

export interface Deployment {
  name: string
  numDetections: number
  numEvents: number
  numSourceImages: number
}

const columns = [
  {
    id: 'deployment',
    name: 'Deployment',
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.name} theme={CellTheme.Primary} />
    ),
  },
  {
    id: 'sessions',
    name: 'Sessions',
    textAlign: TextAlign.Right,
    renderCell: (item: Deployment) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    name: 'Images',
    textAlign: TextAlign.Right,
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.numSourceImages} />
    ),
  },
  {
    id: 'detections',
    name: 'Detections',
    textAlign: TextAlign.Right,
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
]

export const Deployments = () => {
  return (
    <div className={styles.wrapper}>
      <Table items={deployments} columns={columns}></Table>
    </div>
  )
}
