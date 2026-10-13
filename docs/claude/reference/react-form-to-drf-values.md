# React Form Values → DRF Serializer Behavior

How different form values travel from React Hook Form through the API to Django REST Framework serializers and into the database.

## Value mapping for a CharField(null=True, blank=True)

| React form state | JSON sent | DRF `serializer.validated_data` | DB stores |
|---|---|---|---|
| field omitted / `undefined` | key absent | field uses its default (usually `""`) | `""` |
| `null` | `"field": null` | `None` | `NULL` |
| `""` (empty string) | `"field": ""` | `""` | `""` |
| `"http://..."` | `"field": "http://..."` | `"http://..."` | `"http://..."` |

### Key observations

1. **`undefined` and missing keys are equivalent** in JSON — `JSON.stringify({ a: undefined })` produces `{}`. DRF treats missing keys as "not provided" and uses the field's default or marks it as missing (if `required=True`).

2. **Empty string `""` and `null` are different** — DRF distinguishes them. An empty string is a valid value for CharField, while `null` is only accepted when the field has `allow_null=True`.

3. **React Hook Form returns `""` for cleared text inputs**, not `null` or `undefined`. If the intent is "no value", the form must explicitly normalize `""` → `null` before submission.

## Convention in this project

For optional string fields where "no value" is a meaningful state (e.g., `endpoint_url` on ProcessingService), we use `NULL` in the database, not empty string:

- **Frontend**: Normalize empty strings to `null` in the `onSubmit` handler: `endpoint_url: values.endpoint_url || null`
- **Serializer**: Declare with `allow_null=True, allow_blank=False` to reject `""` at the API boundary
- **Model**: Keep `null=True, blank=True` (blank needed for Django admin), add a `save()` guard to normalize `""` → `None`
- **QuerySet filters**: Use `endpoint_url__isnull=True` instead of `Q(isnull=True) | Q(exact="")`

### Example: ProcessingService.endpoint_url

```python
# serializers.py — reject empty string, accept null
endpoint_url = serializers.CharField(
    required=False, allow_null=True, allow_blank=False, max_length=1024
)

# models.py — safety net for admin/shell usage
def save(self, *args, **kwargs):
    if self.endpoint_url == "":
        self.endpoint_url = None
    super().save(*args, **kwargs)
```

```tsx
// form submit — normalize empty input to null
onSubmit={handleSubmit((values) =>
  onSubmit({
    name: values.name,
    customFields: {
      endpoint_url: values.endpoint_url || null,
    },
  })
)}
```

## DRF serializer field flags reference

| Flag | Effect |
|---|---|
| `required=True` (default) | Field must be present in input |
| `required=False` | Field can be omitted; uses default |
| `allow_null=True` | Accepts JSON `null` → Python `None` |
| `allow_blank=True` | Accepts `""` for string fields |
| `allow_blank=False` (default) | Rejects `""` with validation error |

For `CharField` auto-generated from a model field:
- `null=True` on model → `allow_null=True` on serializer
- `blank=True` on model → `allow_blank=True`, `required=False` on serializer

Explicitly declaring the field on the serializer overrides these auto-generated defaults.
