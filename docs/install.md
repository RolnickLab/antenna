# Installation

## Dependencies

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Quick Start

1) Install Docker for your host operating system (Linux, macOS, Windows). Docker Compose `v2.38.2` or later recommended.

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
      It will need to be removed, or you will need to modify its access permissions with the `chown` command if you later want to work on the frontend using the instructions in `ui/README.md`.


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
- NATS dashboard: https://natsdashboard.com/ (Add localhost)

NOTE: If one of these services is not working properly, it could be due another process is using the port. You can check for this with `lsof -i :<PORT_NUMBER>`.

A default user will be created with the following credentials. Use these to log into the web UI or the Django admin.

- Email: `antenna@insectai.org`
- Password: `localadmin`

6) Stop all services with:

    $ docker compose down
