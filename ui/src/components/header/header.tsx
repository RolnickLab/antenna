import { InfoDialog } from 'components/info-dialog/info-dialog'
import { usePages } from 'data-services/hooks/pages/usePages'
import { Link } from 'react-router-dom'
import ami from './ami.png'
import styles from './header.module.scss'

export const Header = () => {
  const { pages = [] } = usePages()

  return (
    <header className={styles.header}>
      <Link to="/">
        <img
          alt="AMI"
          src={ami}
          width={40}
          height={40}
          className={styles.logo}
        />
      </Link>
      <div className={styles.infoPages}>
        {pages.map((page) => (
          <InfoDialog key={page.id} name={page.name} slug={page.slug} />
        ))}
      </div>
    </header>
  )
}
