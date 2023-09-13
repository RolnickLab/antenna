import { ReactNode } from 'react'
import styles from './auth.module.scss'

export const Auth = ({ children }: { children?: ReactNode }) => (
  <div className={styles.wrapper}>
    <div className={styles.imageWrapper}>
      <video autoPlay muted loop>
        <source
          src="https://leps.fieldguide.ai/public/img/videos/caterpillar.mp4"
          type="video/mp4"
        ></source>
      </video>
    </div>
    <div className={styles.content}>{children}</div>
  </div>
)
