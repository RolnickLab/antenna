from rest_framework.pagination import LimitOffsetPagination

from ami.main.api.permissions import add_collection_level_permissions


class LimitOffsetPaginationWithPermissions(LimitOffsetPagination):
    def get_paginated_response(self, data):
        paginated_response = super().get_paginated_response(data=data)
        paginated_response.data = add_collection_level_permissions(
            user=self.request.user, response_data=paginated_response.data
        )
        return paginated_response
