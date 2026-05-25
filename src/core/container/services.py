from __future__ import annotations

from src.core.container.infrastructure import InfrastructureContainer
from src.core.container.repositories import RepositoryContainer


class ServiceContainer:
    """Ленивая инициализация сервисов."""
    def __init__(
        self,
        infra: InfrastructureContainer,
        repos: RepositoryContainer,
    ) -> None:
        self._infra = infra
        self._repos = repos
