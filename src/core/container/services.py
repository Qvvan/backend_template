from src.core.config import Config
from src.core.container.infrastructure import InfrastructureContainer
from src.core.container.repositories import RepositoryContainer


class ServiceContainer:
    """Ленивая инициализация сервисов."""

    __slots__ = (
        "_config",
        "_infra",
        "_repos",
    )

    def __init__(
        self,
        config: Config,
        infra: InfrastructureContainer,
        repos: RepositoryContainer,
    ) -> None:
        self._config = config
        self._infra = infra
        self._repos = repos

