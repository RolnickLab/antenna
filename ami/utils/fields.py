from django.forms import BooleanField
from rest_framework.request import Request


def url_boolean_param(request: Request, param: str, default: bool = False) -> bool:
    """
    The presence of the parameter in the query string with no value indicates True.

    If the parameter is present and has a value, it is parsed as a BooleanField.
    Which means that "true", "True", "1", and "yes" are all True, and everything
    else is False.
    """
    try:
        value = request.query_params[param]
    except KeyError:
        value = False
    else:
        if value == "":
            value = True
        else:
            value = BooleanField(required=False).clean(value)

    return value or default
