# Automated Monitoring of Insects ML Platform

Platform for processing and reviewing images from automated insect monitoring stations. Intended for collaborating on multi-deployment projects, maintaining metadata and orchestrating multiple machine learning pipelines for analysis.

[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

## Quick Start

Antenna uses [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/) to run all services locally for development.

1) Install Docker for your host operating (Linux, macOS, Windows). Docker Compose `v2.38.2` or later recommended.

2) Add the following to your `/etc/hosts` file in order to see and process the demo source images. This makes the hostname `minio` and `django` alias for `localhost` so the same image URLs can be viewed in the host machine's web browser and be processed by the ML services. This can be skipped if you are using an external image storage service.

```
    127.0.0.1 minio
    127.0.0.1 django
```
3) The following commands will build all services, run them in the background, and then stream the logs.
   1) Standard development: will use a pre-built version of the frontend that will not have hot-reloading enabled. However, it will make startup time faster when restarting the stack.
      ```sh
      # Start the whole compose stack
      docker compose up -d

      # To stream the logs
      docker compose logs -f django celeryworker ui
      # Ctrl+c to close the logs

      NOTE: If you see docker build errors such as `At least one invalid signature was encountered`, these could happen if docker runs out of space. Commands like `docker image prune -f` and `docker system prune` can be helpful to clean up space.

      ```
      To update the UI Docker container, use the following command to rebuild the frontend and
      then refresh your browser after.
      ```sh
      docker compose build ui && docker compose up ui -d
      ```

   2) **With hot reloading UI**: Hot reload is enabled for frontend development, but the primary web interface will be slow to load when it first starts or restarts.
      ```sh
      # Stop the production ui first, then start with ui-dev profile
      docker compose stop ui
      docker compose --profile ui-dev up -d

      # Or in one command, scale ui to 0 and start ui-dev
      docker compose --profile ui-dev up -d --scale ui=0

      # To stream the logs
      docker compose logs -f django celeryworker ui-dev

      # To stop the ui-dev container, you must specify the profile when running `down` or `stop`
      docker compose --profile ui-dev down
      # Or!
      docker compose --profile "*" down
      ```
      _**Note that this will create a `ui/node_modules` folder if one does not exist yet. This folder is created by the mounting of the `/ui` folder
      for the `ui-dev` service, and is written by a `root` user.
      It will need to be removed, or you will need to modify its access permissions with the `chown` command if you later want to work on the frontend using the [instructions here](#frontend)._


4) Optionally, run additional ML processing services: `processing_services` defines ML backends which wrap detections in our FastAPI response schema. The `example` app demos how to add new pipelines, algorithms, and models. See the detailed instructions in `processing_services/README.md`.

```
docker compose -f processing_services/example/docker-compose.yml up -d
# Once running, in Antenna register a new processing service called: http://ml_backend_example:2000
```

5) Access the platform with the following URLs:

- Primary web interface: http://localhost:4000
- API browser: http://localhost:8000/api/v2/
- Django admin: http://localhost:8000/admin/
- OpenAPI / Swagger documentation: http://localhost:8000/api/v2/docs/
- Minio UI: http://minio:9001, Minio service: http://minio:9000

NOTE: If one of these services is not working properly, it could be due another process is using the port. You can check for this with `lsof -i :<PORT_NUMBER>`.

A default user will be created with the following credentials. Use these to log into the web UI or the Django admin.

- Email: `antenna@insectai.org`
- Password: `localadmin`

6) Stop all services with:

    $ docker compose down


## Development

Install the pre-commit tool to run linting & formatting checks _before_ each git commit. It's typical to install this tool using your system-wide python.

```
pip install pre-commit  # Install pre-commit system-wide
pre-commit install  # Install the hook for our project
```

If using VS Code, install the [formatting extensions](.vscode/extensions.json) that are automatically suggested for the project (e.g. black). Format-on-save should be turned on by default from the project's [vscode settings file](.vscode/settings.json).

### Frontend

#### Dependencies

- [Node.js](https://nodejs.org/en/download/)
- [Yarn](https://yarnpkg.com/getting-started/install)

#### Configuration

By default this will try to connect to http://localhost:8000 for the backend API. Use the env var `API_PROXY_TARGET` to change this. You can create multiple `.env` files in the `ui/` directory for different environments or configurations. For example, use `yarn start --mode staging` to load `.env.staging` and point the `API_PROXY_TARGET` to a remote backend.

#### Installation

Note: if you installed the ui using Docker first (as instructed in the quick-start) then your local `node_modules/` directory will be owned by root. Change the permissions with:
`sudo chown -R ${UID}:${UID} ui/node_modules`. The version of Node on your host machine must match that of the Docker container (which will be the case if you follow the `nvm` instructions below.)

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

All backend packages are installed in the docker containers, however for faster auto-completion and intellisense, you can install them on the host machine:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```

#### Helpful Commands

##### Run the docker compose stack in the background

    docker compose up -d

##### Watch the logs of Django & the backend workers

    docker compose logs -f django celeryworker

##### Watch the logs of all services:

    docker compose logs -f

##### Create a super user account:

    docker compose run --rm django python manage.py createsuperuser

##### Create a fresh demo project with synthetic data

```bash
docker compose run --rm django python manage.py create_demo_project
```

##### Run tests

```bash
docker compose run --rm django python manage.py test
```

##### Run tests with a specific pattern in the test name

```bash
docker compose run --rm django python manage.py test -k pattern
```

##### Run tests and drop into interactive shell on failure

```bash
docker compose run --rm django python manage.py test -k pattern --failfast --pdb
```

##### Speed up development of tests by reusing the db between test runs

```bash
docker compose run --rm django python manage.py test --keepdb
```

##### Run management scripts

```bash
docker compose run django python manage.py --help
```

##### Launch the Django shell:

    docker compose exec django python manage.py shell

    >>> from ami.main.models import SourceImage, Occurrence
    >>> SourceImage.objects.all(project__name='myproject')

##### Install backend dependencies locally for IDE support (Intellisense, etc):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```

##### Build the frontend assets through Docker

```bash
docker compose run --rm ui yarn build
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

## Debugging with VS Code

Antenna supports remote debugging with debugpy for both Django and Celery services.

### Setup

1. Copy or link the override example file:
   ```bash
   cp docker-compose.override-example.yml docker-compose.override.yml
   # OR
   ln -s docker-compose.override-example.yml docker-compose.override.yml
   ```

2. Start services normally:
   ```bash
   docker compose up
   ```

3. In VS Code, open the Debug panel (Ctrl+Shift+D) and select one of:
   - **Attach: Django** - Debug the Django web server (port 5678)
   - **Attach: Celeryworker** - Debug the Celery worker (port 5679)
   - **Attach: Django + Celery** - Debug both simultaneously

4. Click the green play button or press F5 to attach the debugger

### Setting Breakpoints

- Set breakpoints in your Python code by clicking in the left margin of the editor
- When the code executes, the debugger will pause at your breakpoints
- Use the Debug Console to inspect variables and execute expressions

### Troubleshooting

- **Connection refused**: Make sure you copied `docker-compose.override-example.yml` to `docker-compose.override.yml`
- **Debugger not stopping**: Verify breakpoints are set in code that actually executes
- **Port conflicts**: Check that ports 5678 and 5679 aren't already in use on your host machine
- **Auto-reload**: Note that auto-reloading is disabled when debugging. You will need to manually restart the services to see code changes.

### Disabling Debug Mode

To disable debugging and return to normal operation:

```bash
rm docker-compose.override.yml
docker compose restart django celeryworker
```
