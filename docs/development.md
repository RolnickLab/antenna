# Development

Install the pre-commit tool to run linting & formatting checks _before_ each git commit. It's typical to install this tool using your system-wide python.

```
pip install pre-commit  # Install pre-commit system-wide
pre-commit install  # Install the hook for our project
```

## Frontend

See `ui/README.md` for information about the frontend!

## Backend

### Helpful Commands

#### Run the Docker compose stack in the background

    docker compose up -d

#### Rebuild Docker images

    docker compose build

#### Watch the logs of Django & the backend workers

    docker compose logs -f django celeryworker

#### Watch the logs of all services:

    docker compose logs -f

#### Create a super user account:

    docker compose run --rm django python manage.py createsuperuser

#### Create a fresh demo project with synthetic data

```bash
docker compose run --rm django python manage.py create_demo_project
```

#### Run tests

```bash
docker compose -f docker-compose.ci.yml run --rm django python manage.py test
```

#### Run tests with a specific pattern in the test name

```bash
docker compose -f docker-compose.ci.yml run --rm django python manage.py test -k pattern
```

#### Run tests and drop into interactive shell on failure

```bash
docker compose -f docker-compose.ci.yml run --rm django python manage.py test -k pattern --failfast --pdb
```

#### Speed up development of tests by reusing the db between test runs

```bash
docker compose -f docker-compose.ci.yml run --rm django python manage.py test --keepdb
```

#### Run management scripts

```bash
docker compose run django python manage.py --help
```

#### Launch the Django shell:

    docker compose exec django python manage.py shell

    >>> from ami.main.models import SourceImage, Occurrence
    >>> SourceImage.objects.all(project__name='myproject')

#### Install backend dependencies locally for IDE support (Intellisense, etc):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```

#### Build the frontend assets through Docker

```bash
docker compose run --rm ui yarn build
```

#### Generate OpenAPI schema

```bash
docker compose run --rm django python manage.py spectacular --api-version 'api' --format openapi --file ami-openapi-schema.yaml
```

#### Generate TypeScript types from OpenAPI schema

```bash
docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate -i /local/ami-openapi-schema.yaml -g typescript-axios -o /local/ui/src/api-schema.d.ts
```

#### Generate diagram graph of Django models & relationships (Graphviz required)

```bash
docker compose run --rm django python manage.py graph_models -a -o models.dot --dot
dot -Tsvg  models.dot > models.svg
```

## Project Data Storage

Each project manages its own external data storage where the AMI Platform will index and process images. This is most typically a public or private S3 bucket at a cloud provider that is not AWS. For example, the Swift object storage service at Compute Canada or a university's own storage service.

To test the S3 storage backend locally, Minio is configured to run as part of the docker compose stack.

To configure a project connect to the Minio service, you can use the following config:

```
Endpoint URL: http://minio:9000
Access key: amistorage
Secret access key: amistorage
Public base URL: http://minio:9000/ami/
Bucket: ami
```

- Open the Minio web interface at http://localhost:9001 and login with the access key and secret access key.
- Upload some test images to a subfolder in the `ami` bucket (one subfolder per deployment)
- Give the bucket or folder anonymous access using the "Anonymous access" button in the Minio web interface.
- Both public and private buckets with presigned URLs should work.
- Add entries to your local `/etc/hosts` file to map the `minio` and `django` hostnames to localhost so the same image URLs can be viewed in your host machine's browser and processed in the backend containers.

```
127.0.0.1 minio
127.0.0.1 django
```

## Email

The local environment uses the `console` email backend. To view emails sent by the platform, check the console output (run the `docker compose logs -f django celeryworker` command).

Links and the site name in account emails, such as password resets, come from the Site record. In the Django admin (Sites), set the Domain name to your web app's hostname and the Display name to the name users should see, then restart the web container.

## Database

The local environment uses a local PostgreSQL database in a Docker container.

### Backup and Restore

    docker compose run --rm postgres backup

### Reset the database

    docker compose run --rm django python manage.py reset_db

### Show backups

    docker compose run --rm postgres backups

### Restore a backup

    docker compose run --rm postgres restore <backup_file_name>

### Load fixtures with test data

    docker compose run --rm django python manage.py migrate

## Local packages

All backend packages are installed in the docker containers, however for faster auto-completion and intellisense, you can install them on the host machine:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```
