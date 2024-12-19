import { Identification } from 'data-services/models/occurrence-details'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { AlgorithmDetails } from 'pages/occurrence-details/algorithm-details/algorithm-details'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
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
}: IdentificationSummaryProps) => {
  const formattedTime = getFormatedDateTimeString({
    date: new Date(identification.createdAt),
  })

  return (
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
        <Tooltip content={formattedTime}>
          <span className={styles.username}>
            {user?.name ?? translate(STRING.MACHINE_SUGGESTION)}
          </span>
        </Tooltip>
      </div>
      {identification.algorithm && (
        <AlgorithmDetails algorithm={identification.algorithm} />
      )}

      {identification.score && (
        <div className={styles.AlgorithmDetails}>
          <span>{`${identification.score.toPrecision(4)}`}</span>
        </div>
      )}
      {identification.terminal !== undefined && (
        <div className={styles.AlgorithmDetails}>
          {identification.terminal
            ? translate(STRING.TERMINAL_CLASSIFICATION)
            : translate(STRING.INTERMEDIATE_CLASSIFICATION)}
        </div>
      )}
      <div className={styles.AlgorithmDetails}>
        <span>{formattedTime}</span>
      </div>
    </div>
  )
}
