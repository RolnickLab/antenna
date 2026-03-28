from rest_framework import serializers


class ClientInfoSerializer(serializers.Serializer):
    """
    Validated client_info from processing service requests.

    Client-reported fields (all optional):
        hostname, software, version, platform, pod_name, extra

    Server-observed fields (added by get_client_info(), not sent by client):
        ip, user_agent
    """

    hostname = serializers.CharField(max_length=255, required=False, default="")
    software = serializers.CharField(max_length=100, required=False, default="")
    version = serializers.CharField(max_length=50, required=False, default="")
    platform = serializers.CharField(max_length=100, required=False, default="")
    pod_name = serializers.CharField(max_length=255, required=False, default="")
    extra = serializers.DictField(required=False, default=dict)


def get_client_info(request) -> dict:
    """
    Extract client_info from request body, merged with server-observed values.

    Server-observed fields (ip, user_agent) are always present.
    Client-reported fields come from request.data["client_info"] when provided.
    """
    raw = request.data.get("client_info") or {}
    serializer = ClientInfoSerializer(data=raw)
    if serializer.is_valid():
        info = serializer.validated_data
    else:
        info = {}

    info.setdefault("ip", _get_client_ip(request))
    info.setdefault("user_agent", request.headers.get("user-agent", ""))
    return info


def _get_client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
