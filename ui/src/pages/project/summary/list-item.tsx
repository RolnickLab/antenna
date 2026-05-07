import { ImageIcon, UserIcon } from 'lucide-react'

export const ListItem = ({
  count,
  item,
}: {
  count?: number
  item: {
    image: { src?: string; variant?: 'default' | 'user' }
    text: string
    title?: string
  }
}) => (
  <div className="flex items-center gap-4 p-2 pr-4 border-border border-b last:border-none">
    {item.image.variant === 'user' ? (
      <UserImage image={item.image.src} />
    ) : (
      <Image image={item.image.src} />
    )}
    <div className="flex flex-col">
      <div className="flex items-center gap-4">
        {item.title ? <span className="font-medium">{item.title}</span> : null}
      </div>
      <span>{item.text}</span>
    </div>
    {count !== undefined ? (
      <span className="grow text-right">{count.toLocaleString()}</span>
    ) : null}
  </div>
)

const Image = ({ image }: { image?: string }) => (
  <div className="flex items-center justify-center w-12 h-12 border border-border rounded-md text-muted-foreground overflow-hidden">
    {image ? (
      <img className="object-cover" alt="" src={image} />
    ) : (
      <ImageIcon className="w-4 h-4" />
    )}
  </div>
)

const UserImage = ({ image }: { image?: string }) => (
  <div className="flex items-center justify-center w-12 h-12 border border-border rounded-full text-muted-foreground overflow-hidden">
    {image ? (
      <img className="object-cover" alt="" src={image} />
    ) : (
      <UserIcon className="w-4 h-4" />
    )}
  </div>
)
