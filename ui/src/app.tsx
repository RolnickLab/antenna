import React from 'react'
import styles from './app.module.scss'

export const App = () => {
  return (
    <div className={styles.wrapper}>
      <header className={styles.header}></header>
      <main className={styles.main}>
        <div className={styles.content}></div>
      </main>
    </div>
  )
}
