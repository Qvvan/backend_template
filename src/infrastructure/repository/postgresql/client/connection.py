import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import quote_plus
import asyncpg

from src.core.logger import AppLogger
from src.infrastructure.repository.postgresql.client.transaction_executor import PostgresTransactionExecutor
from src.interfaces.clients.db.connection import IDBTransactional


class PostgresConnectionPool(IDBTransactional):
    __slots__ = ("_logger", "_pool", "dsn", "echo", "pool_size", "_command_timeout", "_statement_cache_size", "_connect_lock")

    def __init__(
        self,
        *,
        logger: AppLogger,
        user: str,
        password: str,
        host: str,
        port: int,
        database: str,
        echo: bool = False,
        pool_size: int = 5,
        command_timeout: int = 10,
        statement_cache_size: int = 256,
    ):
        self.dsn = f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{database}"
        self.echo = echo
        self.pool_size = pool_size
        self._logger = logger
        self._command_timeout = command_timeout
        self._statement_cache_size = statement_cache_size
        self._pool: asyncpg.Pool | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Создает пул соединений с БД"""
        async def init_connection(connection: asyncpg.Connection) -> None:
            await connection.set_type_codec(
                'uuid',
                encoder=str,
                decoder=str,
                schema='pg_catalog'
            )

        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=self.pool_size // 2,
            max_size=self.pool_size,
            command_timeout=self._command_timeout,
            statement_cache_size=self._statement_cache_size,
            init=init_connection
        )
        if self._pool is None:
            raise RuntimeError("Failed to create connection pool")

        if self.echo:
            self._logger.info(f"Database pool created with {self.pool_size} connections")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        if not self._pool:
            async with self._connect_lock:
                if not self._pool:
                    await self.connect()

        async with self._pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[PostgresTransactionExecutor, None]:
        async with self.get_connection() as conn: # type: ignore[override]
            async with conn.transaction():
                yield PostgresTransactionExecutor(conn)

    async def close(self) -> None:
        """Закрытие пула соединений"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def health_check(self) -> bool:
        try:
            async with asyncio.timeout(5):
                async with self.get_connection() as conn:
                    await conn.execute("SELECT 1")
                    return True
        except Exception as e:
            self._logger.error(f"Health check failed: {e!s}")
            return False
