import { Identification } from 'data-services/models/occurrence-details'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { Icon, IconTheme, IconType } from '../../icon/icon'
import styles from './identification-summary.module.scss'

interface IdentificationSummaryProps {
  user?: {
    name: string
    image?: string
  }
  identification: Identification
}

export const IdentificationSummary = ({
  user,
  identification,
}: IdentificationSummaryProps) => (
  <div className={styles.wrapper}>
    <div className={styles.user}>
      {user ? (
        <div className={styles.profileImage}>
          {user.image ? (
            <img src={user.image} alt="" />
          ) : (
            <Icon
              type={IconType.Photograph}
              theme={IconTheme.Primary}
              size={16}
            />
          )}
        </div>
      ) : (
        <Icon type={IconType.BatchId} theme={IconTheme.Primary} size={16} />
      )}
      <span className={styles.username}>
        {user?.name ?? translate(STRING.MACHINE_SUGGESTION)}
      </span>
    </div>
    {identification.algorithm && (
      <Link to={identification.algorithm.uri}>
        <Tooltip content={identification.algorithm.description}>
          <div className={styles.details}>
            {identification.algorithm.name}
            <Icon
              type={IconType.ExternalLink}
              theme={IconTheme.Primary}
              size={16}
            />
          </div>
        </Tooltip>
      </Link>
    )}
    {identification.score && (
      <div className={styles.details}>
        <span>
          {translate(STRING.FIELD_LABEL_SCORE)}{' '}
          {`${identification.score.toPrecision(4)}`}
        </span>
        {identification.terminal !== undefined && (
          <span>
            {' | '}
            {identification.terminal
              ? translate(STRING.TERMINAL_CLASSIFICATION)
              : translate(STRING.INTERMEDIATE_CLASSIFICATION)}
          </span>
        )}
      </div>
    )}
  </div>
)
