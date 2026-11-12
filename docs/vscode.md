# Debugging with VS Code

Antenna supports remote debugging with debugpy for both Django and Celery services.

Install the [formatting extensions](../.vscode/extensions.json) that are automatically suggested for the project (e.g. black). Format-on-save should be turned on by default from the project's [vscode settings file](.vscode/settings.json).

## Setup

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

## Setting Breakpoints

- Set breakpoints in your Python code by clicking in the left margin of the editor
- When the code executes, the debugger will pause at your breakpoints
- Use the Debug Console to inspect variables and execute expressions

## Troubleshooting

- **Problems after pull**: If Dockerfiles or dependencies have been updated, make sure to rebuild the Docker images: `docker compose build`. For source code changes, this is not needed.
- **Connection refused**: Make sure you copied `docker-compose.override-example.yml` to `docker-compose.override.yml`
- **Debugger not stopping**: Verify breakpoints are set in code that actually executes
- **Port conflicts**: Check that ports 5678 and 5679 aren't already in use on your host machine
- **Auto-reload**: Note that auto-reloading is disabled when debugging. You will need to manually restart the services to see code changes.

## Disabling Debug Mode

To disable debugging and return to normal operation:

```bash
rm docker-compose.override.yml
docker compose restart django celeryworker
```
