"""
Standard pagination class used across all list endpoints.

Design decisions:
- Default page size: 20 (matching approved API spec)
- Maximum page size: 100 (prevents abuse)
- Page number pagination rather than cursor — simpler for filtering + sorting use cases
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "next": {"type": "string", "nullable": True},
                "previous": {"type": "string", "nullable": True},
                "total_pages": {"type": "integer"},
                "current_page": {"type": "integer"},
                "results": schema,
            },
        }


class MessagePagination(PageNumberPagination):
    """
    Pagination for chat messages.
    Default 50 per load (approved spec); supports loading older messages.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"
    ordering = "-created_at"  # newest first (reversed in serializer for display)
