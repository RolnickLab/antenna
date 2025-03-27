import { FormRow, FormSection } from 'components/form/layout/layout'
import { useAlgorithmDetails } from 'data-services/hooks/algorithm/useAlgorithmDetails'
import { Algorithm } from 'data-services/models/algorithm'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const AlgorithmDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { algorithm, isLoading, error } = useAlgorithmDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.ALGORITHMS({
              projectId: projectId as string,
            }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
      >
        <Dialog.Header
          title={translate(STRING.ENTITY_DETAILS, {
            type: _.capitalize(translate(STRING.ENTITY_TYPE_ALGORITHM)),
          })}
        />
        <div className={styles.content}>
          {algorithm ? <AlgorithmDetailsContent algorithm={algorithm} /> : null}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const AlgorithmDetailsContent = ({ algorithm }: { algorithm: Algorithm }) => (
  <>
    <FormSection title={translate(STRING.SUMMARY)}>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_ID)}
          value={algorithm.id}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_NAME)}
          value={algorithm.name}
        />
      </FormRow>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_KEY)}
          value={algorithm.key}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_TASK_TYPE)}
          value={algorithm.taskType}
        />
      </FormRow>

      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_CREATED_AT)}
          value={algorithm.createdAt}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
          value={algorithm.updatedAt}
        />
      </FormRow>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_URI)}
          value={algorithm.uri}
          to={algorithm.uri}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_VERSION)}
          value={algorithm.version}
        />
      </FormRow>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_DESCRIPTION)}
          value={algorithm.description}
        />
      </FormRow>
    </FormSection>
    <FormSection title={translate(STRING.CATEGORY_MAP_DETAILS)}>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_CATEGORY_MAP_ID)}
          value={algorithm.categoryMapID}
          to={algorithm.categoryMapURI}
        />
      </FormRow>
    </FormSection>
  </>
)
