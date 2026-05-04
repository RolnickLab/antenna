# Process Single Image Command

A Django management command for processing a single image through a pipeline. Useful for testing, debugging, and reprocessing individual images.

## Usage

### With Wait Flag (Monitor Progress)

```bash
docker compose run --rm web python manage.py process_single_image 12345 --pipeline 1 --wait
```
