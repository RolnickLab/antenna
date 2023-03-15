import React from 'react'
import { DeploymentsTable } from './deployments-table/deployments-table'
import styles from './deployments.module.scss'

export const Deployments = () => {
  return (
    <div className={styles.wrapper}>
      <DeploymentsTable />
    </div>
  )
}
