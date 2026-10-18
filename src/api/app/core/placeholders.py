"""Helper for endpoints that are planned but not implemented yet."""

from fastapi import HTTPException, status


def not_implemented(feature: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{feature} is planned but not implemented yet.",
    )
