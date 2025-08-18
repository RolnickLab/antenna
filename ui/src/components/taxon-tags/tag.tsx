import classNames from 'classnames'

export const Tag = ({
  name,
  className,
}: {
  name: string
  className?: string
}) => (
  <div
    className={classNames(
      'h-6 inline-flex items-center px-3 rounded-full bg-primary text-primary-foreground body-small font-medium lowercase',
      className
    )}
  >
    {name}
  </div>
)
