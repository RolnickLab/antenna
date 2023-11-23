import { FormRow } from 'components/form/layout/layout'
import { Pipeline } from 'data-services/models/pipeline'
import { InputValue } from 'design-system/components/input/input'
import { StatusBullet } from 'design-system/components/wizard/status-bullet/status-bullet'
import * as Wizard from 'design-system/components/wizard/wizard'
import { useState } from 'react'

export const PipelineStages = ({ pipeline }: { pipeline: Pipeline }) => {
  const [activeStage, setActiveStage] = useState<string>()

  return (
    <Wizard.Root value={activeStage} onValueChange={setActiveStage}>
      {pipeline.stages.map((stage, index) => (
        <Wizard.Item key={index} value={stage.key}>
          <Wizard.Trigger title={stage.name}>
            <StatusBullet value={index + 1} />
          </Wizard.Trigger>
          <Wizard.Content>
            <FormRow>
              {stage.fields.map((field) => (
                <InputValue
                  key={field.key}
                  label={field.label}
                  value={field.value}
                />
              ))}
            </FormRow>
          </Wizard.Content>
        </Wizard.Item>
      ))}
    </Wizard.Root>
  )
}
