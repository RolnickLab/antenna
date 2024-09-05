# Automated Monitoring of Insects ML Platform

Platform for processing and reviewing images from automated insect monitoring stations. Intended for collaborating on multi-deployment projects, maintaining metadata and orchestrating multiple machine learning pipelines for analysis.

[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

## Quick Start

The platform uses Docker Compose to run all services locally for development. Install Docker Desktop and run the following command:

    $ docker compose up

- Web UI: http://localhost:4000
- API Browser: http://localhost:8000/api/v2/
- Django admin: http://localhost:8000/admin/
- OpenAPI / Swagger Docs: http://localhost:8000/api/v2/docs/

If using VSCode, configure the appropriate extensions and the pre-commit hook for linting/formatting.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
pre-commit install
pre-commit run --all-files
```

## Development

### Frontend

#### Dependencies

- [Node.js](https://nodejs.org/en/download/)
- [Yarn](https://yarnpkg.com/getting-started/install)

#### Configuration

By default this will try to connect to http://localhost:8000 for the backend API. Use the env var `API_PROXY_TARGET` to change this. You can create multiple `.env` files in the `ui/` directory for different environments or configurations. For example, use `yarn start --mode staging` to load `.env.staging` and point the `API_PROXY_TARGET` to a remote backend.

#### Installation

```bash
# Enter into the ui directory
cd ui
# Install Node Version Manager
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# Install required Node.js version
nvm install
# Install Yarn dependencies
yarn install
# Start the frontend
yarn start
```

Visit http://localhost:3000/

### Backend

#### Dependencies

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)


#### Helpful Commands

##### Run the docker compose stack in the background

    docker compose up -d

##### Watch the logs of Django & the backend workers

    docker compose logs -f django celeryworker

##### Watch the logs of all services:

    docker compose logs -f

#####  Create a super user account:

    docker compose run --rm django python manage.py createsuperuser

##### Run tests

```bash
docker compose run --rm django python manage.py test
```

##### Run tests with a specific pattern in the test name

```bash
docker compose run --rm django python manage.py test -k pattern
```

##### Launch the Django shell:

    docker-compose exec django python manage.py shell

    >>> from ami.main.models import SourceImage, Occurrence
    >>> SourceImage.objects.all(project__name='myproject')

##### Install backend dependencies locally for IDE support (Intellisense, etc):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```

##### Generate OpenAPI schema

```bash
docker compose run --rm django python manage.py spectacular --api-version 'api' --format openapi --file ami-openapi-schema.yaml
```

##### Generate TypeScript types from OpenAPI schema

```bash
docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate -i /local/ami-openapi-schema.yaml -g typescript-axios -o /local/ui/src/api-schema.d.ts
```

##### Generate diagram graph of Django models & relationships (Graphviz required)

```bash
docker compose run --rm django python manage.py graph_models -a -o models.dot --dot
dot -Tsvg  models.dot > models.svg
```

## Project Data Storage

Each project manages its own external data storage where the AMI Platform will index and process images. This is most typically a public or private S3 bucket at a cloud provider that is not AWS. For example
the Swift object storage service at Compute Canada or a university's own storage service.

To test the S3 storage backend locally, Minio is configured to run as part of the docker compose stack.

To configure a project connect to the Minio service, you can use the following config:

```
Endpoint URL: http://minio:9000
Access key: amistorage
Secret access key: amistorage
Public base URL: http://localhost:9000/ami/
Bucket: ami
```

- Open the Minio web interface at http://localhost:9001 and login with the access key and secret access key.
- Upload some test images to a subfolder in the `ami` bucket (one subfolder per deployment)
- Give the bucket or folder anonymous access using the "Anonymous access" button in the Minio web interface.
- You _can_ test private buckets and presigned URLs, but you will need to add an entry to your local /etc/hosts file to map the `minio` hostname to localhost.

## Email

The local environment uses the `console` email backend. To view emails sent by the platform, check the console output (run the `docker compose logs -f django celeryworker` command).

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
