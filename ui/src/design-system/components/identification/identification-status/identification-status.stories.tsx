import { ComponentMeta } from '@storybook/react'
import { IdentificationStatus } from './identification-status'

type Meta = ComponentMeta<typeof IdentificationStatus>

export default {
  title: 'Components/Identification/IdentificationStatus',
  component: IdentificationStatus,
  argTypes: {
    score: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
    scoreThreshold: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
  },
} as Meta

export const Default: Meta = {
  args: {
    isVerified: false,
    score: 0.7,
    scoreThreshold: 0.6,
  },
}

export const Verified: Meta = {
  args: {
    isVerified: true,
    score: 0.7,
    scoreThreshold: 0.6,
  },
}

export const BelowThreshold: Meta = {
  args: {
    isVerified: false,
    score: 0.5,
    scoreThreshold: 0.6,
  },
}
