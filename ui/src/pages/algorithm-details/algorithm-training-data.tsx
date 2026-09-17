import { useTrainingDataSummary } from 'data-services/hooks/algorithm/useTrainingDataSummary'
import { Algorithm } from 'data-services/models/algorithm'
import { InputValue } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const AlgorithmTrainingData = ({
  algorithm,
}: {
  algorithm: Algorithm
}) => {
  const { projectId } = useParams()
  const { summary } = useTrainingDataSummary(projectId, algorithm.key)

  if (!summary) {
    return null
  }

  return (
    <>
      <InputValue
        label={translate(STRING.FIELD_LABEL_TRAINING_IMAGES_READY)}
        value={summary.cropsReady}
      />
      <InputValue
        label={translate(STRING.FIELD_LABEL_SPECIES)}
        value={summary.species}
      />
      <InputValue
        label={translate(STRING.FIELD_LABEL_CROPS_WITHOUT_EMBEDDING)}
        value={summary.cropsWithoutEmbedding}
      />
    </>
  )
}
