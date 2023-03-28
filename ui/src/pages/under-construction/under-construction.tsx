import React from 'react'
import styles from './under-construction.module.scss'

interface UnderConstructionProps {
  message?: string
}

export const UnderConstruction = ({
  message = 'This page is under construction!',
}: UnderConstructionProps) => {
  return <h1 className={styles.message}>{message} 🦋</h1>
}
