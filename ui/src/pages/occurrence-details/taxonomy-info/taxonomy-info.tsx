import styles from './taxonomy-info.module.scss'

const taxonomy = {
  image:
    'https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Meropleon_diversicolor_-_Multicolored_Sedgeminer_Moth_%289810621354%29.jpg/440px-Meropleon_diversicolor_-_Multicolored_Sedgeminer_Moth_%289810621354%29.jpg',
  description:
    'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum sodales cursus porta. Proin nec quam turpis.',
}

export const TaxonomyInfo = () => (
  <div className={styles.container}>
    <img src={taxonomy.image} />
    <div className={styles.content}>
      <p>{taxonomy.description}</p>
    </div>
  </div>
)
