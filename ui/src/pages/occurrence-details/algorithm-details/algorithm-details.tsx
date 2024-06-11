import { Algorithm } from 'data-services/models/algorithm'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './algorithm-details.module.scss'

export const AlgorithmDetails = ({ algorithm }: { algorithm: Algorithm }) => (
  <Tooltip content={algorithm.description}>
    <div className={styles.algorithmDetails}>{algorithm.name}</div>
  </Tooltip>
)
