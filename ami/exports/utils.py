import logging

from django.conf import settings
from django.db import models
from django.test import RequestFactory
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.versioning import NamespaceVersioning

logger = logging.getLogger(__name__)


def generate_fake_request(
    path: str = "/api/v2/occurrences/",
    method: str = "GET",
    query_params: dict = None,
    headers: dict = None,
) -> Request:
    """
    Generate a fake DRF request object to mimic an actual API request.

    Args:
        path (str): The API endpoint path (default: occurrences list view).
        method (str): The HTTP method (default: GET).
        query_params (dict, optional): Query parameters to include in the request.
        headers (dict, optional): Additional HTTP headers.

    Returns:
        Request: A DRF request object that mimics a real API request.
    """

    from urllib.parse import urlencode

    factory = RequestFactory()

    # Construct the full URL with query parameters
    full_path = f"{path}?{urlencode(query_params)}" if query_params else path

    # Create the base request
    request_method = getattr(factory, method.lower(), factory.get)
    raw_request = request_method(full_path)

    # Set HTTP Host
    raw_request.META["HTTP_HOST"] = getattr(settings, "EXTERNAL_HOSTNAME", "localhost")

    # Add additional headers if provided
    if headers:
        for key, value in headers.items():
            raw_request.META[f"HTTP_{key.upper().replace('-', '_')}"] = value

    # Wrap in DRF's Request object
    fake_request = Request(raw_request)

    # Set versioning details
    fake_request.version = "api"
    fake_request.versioning_scheme = NamespaceVersioning()

    return fake_request


def apply_filters(queryset, filters, filter_backends):
    """
    Apply filtering backends to the given queryset using the provided filter query params.
    """
    request = generate_fake_request(query_params=filters)
    logger.debug(f"Queryset count before filtering : {queryset.count()}")
    logger.debug(f"Filter values : {filters}")
    logger.debug(f"Filter backends : {filter_backends}")
    for backend in filter_backends:
        queryset = backend().filter_queryset(request, queryset, None)  # `view` is None since we are not using ViewSet
    logger.debug(f"Queryset count after filtering : {queryset.count()}")
    return queryset


def get_data_in_batches(QuerySet: models.QuerySet, Serializer: type[serializers.Serializer], batch_size=100):
    """
    Yield batches of serialized data from a queryset efficiently.
    """
    items = QuerySet.iterator(chunk_size=batch_size)  # Efficient iteration to avoid memory issues
    batch = []

    fake_request = generate_fake_request()
    for i, item in enumerate(items):
        try:
            serializer = Serializer(
                item,
                context={
                    "request": fake_request,
                },
            )

            item_data = serializer.data

            batch.append(item_data)

            # Yield batch once it reaches batch_size
            if len(batch) >= batch_size:
                yield batch
                batch = []  # Reset batch
        except Exception as e:
            logger.warning(f"Error processing occurrence {item.id}: {str(e)}")
            raise e

    if len(batch):
        yield batch  # yield the last batch if total number of records not divisible by batch_size
