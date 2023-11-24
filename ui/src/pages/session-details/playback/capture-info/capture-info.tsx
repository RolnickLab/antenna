import { CaptureDetails } from 'data-services/models/capture-details'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import * as Popover from 'design-system/components/popover/popover'
import { STRING, translate } from 'utils/language'
import styles from './capture-info.module.scss'

export const CaptureInfo = ({ capture }: { capture?: CaptureDetails }) => {
  if (!capture) {
    return (
      <IconButton
        icon={IconType.Info}
        theme={IconButtonTheme.Neutral}
        disabled
      />
    )
  }

  return (
    <Popover.Root>
      <Popover.Trigger>
        <IconButton icon={IconType.Info} theme={IconButtonTheme.Neutral} />
      </Popover.Trigger>
      <Popover.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        align="start"
        hideClose
        side="right"
      >
        <div className={styles.wrapper}>
          <div className={styles.row}>
            <span className={styles.title}>
              {translate(STRING.FIELD_LABEL_TIMESTAMP)}:
            </span>
            <span>{capture.dateTimeLabel}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.title}>
              {translate(STRING.FIELD_LABEL_SIZE)}:
            </span>
            <span>{capture.sizeLabel}</span>
          </div>
          <a
            href={capture.url}
            className={styles.link}
            rel="noreferrer"
            target="_blank"
          >
            <div className={styles.row}>
              <span>{translate(STRING.FIELD_LABEL_SOURCE_IMAGE)}</span>
              <Icon type={IconType.ExternalLink} theme={IconTheme.Primary} />
            </div>
          </a>
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
