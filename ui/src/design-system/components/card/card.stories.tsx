import { ComponentMeta } from '@storybook/react'
import { Card } from './card'

type Meta = ComponentMeta<typeof Card>

export default {
  title: 'Components/Card',
  component: Card,
} as Meta

export const Default: Meta = {
  args: {
    title: 'Lorem ipsum',
    subTitle: 'Lorem ipsum dolor sit amet',
    image: {
      src: 'https://placekitten.com/600/400',
    },
    maxWidth: '320px',
  },
}
