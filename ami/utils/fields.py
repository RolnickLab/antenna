from django.forms import BooleanField
from rest_framework.request import Request


def url_boolean_param(request: Request, param: str, default: bool = False) -> bool:
    value = request.query_params.get(param)
    if value is not None:
        return BooleanField(required=False).clean(value)
    else:
        return default
