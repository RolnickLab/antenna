# Automated Monitoring of Insects ML Platform

Platform for processing and reviewing images from automated insect monitoring stations.


[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

## Quick Start

The project uses docker compose to run all backend services. To start the project, run the following command:

    $ docker-compose up

Explore the API
- Rest Framework: http://localhost:8000/api/v2/
- OpenAPI / Swagger: http://localhost:8000/api/v2/docs/


Install and run the frontend:

```bash
cd ui
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install
yarn install
yarn start
```

Visit http://localhost:3000/


Create a super user account:

    docker compose exec django python manage.py createsuperuser

Access the Django admin:

http://localhost:8000/admin/



## Helpful Commands

Generate OpenAPI schema

```bash
docker-compose -f local.yml run --rm django python manage.py spectacular --api-version 'api' --format openapi --file ami-openapi-schema.yaml
```

Generate TypeScript types from OpenAPI schema

```bash
docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate -i /local/ami-openapi-schema.yaml -g typescript-axios -o /local/ui/src/api-schema.d.ts
```

Generate diagram graph of Django models & relationships (Graphviz required)

```bash
docker compose -f local.yml run --rm django python manage.py graph_models -a -o models.dot --dot
dot -Tsvg  models.dot > models.svg
```

Run tests

```bash
docker-compose -f local.yml run --rm django python manage.py test
```

Run tests with a specific pattern in the test name

```bash
docker-compose -f local.yml run --rm django python manage.py test -k pattern
```


Launch the Django shell:

    docker-compose exec django python manage.py shell

Install dependencies locally for IDE support (Intellisense, etc):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
```


## Dependencies

### Backend
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Frontend
- [Node.js](https://nodejs.org/en/download/)
- [Yarn](https://yarnpkg.com/getting-started/install)


### Frontend

0. Change to the frontend directory:

    ```bash
    $ cd ui
    ```

1. Install Node Version Manager:

    ```bash
    $ curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    ```
2. Install Node.js:

    ```bash
    $ nvm install
    ```

3. Install Yarn:

    ```bash
    $ npm install --global yarn
    ```

4. Install the dependencies:

    ```bash
    $ yarn install
    ```

5. Create a `.env` file in the `frontend` directory with the following content:

    ```bash
    REACT_APP_API_URL=http://localhost:8000
    ```

6. Start the frontend:

    ```bash
    $ yarn start
    ```
