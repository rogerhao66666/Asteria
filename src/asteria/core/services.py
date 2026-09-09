from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


class ServiceRegistry:
    """Explicit process/game service registry keyed by declared service type."""

    __slots__ = ("_services",)

    def __init__(self) -> None:
        self._services: dict[type[object], object] = {}

    def add(self, service_type: type[T], service: T) -> T:
        if service_type in self._services:
            raise ValueError(f"service {service_type.__name__} already registered")
        self._services[service_type] = service
        return service

    def replace(self, service_type: type[T], service: T) -> T:
        self._services[service_type] = service
        return service

    def get(self, service_type: type[T]) -> T:
        try:
            return self._services[service_type]  # type: ignore[return-value]
        except KeyError as exc:
            raise KeyError(
                f"service {service_type.__name__} is not registered"
            ) from exc

    def try_get(self, service_type: type[T]) -> T | None:
        return self._services.get(service_type)  # type: ignore[return-value]

    def remove(self, service_type: type[T]) -> T | None:
        return self._services.pop(service_type, None)  # type: ignore[return-value]

    def clear(self) -> None:
        self._services.clear()
