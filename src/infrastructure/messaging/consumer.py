import asyncio

from src.core.logger import AppLogger
from src.interfaces.messaging.consumer import IConsumer
from src.interfaces.messaging.rabbitmq import IAMQPClient


class BackendConsumer(IConsumer):
    __slots__ = ("_logger", "_rabbit", "_stop_event")

    def __init__(
        self,
        *,
        rabbit: IAMQPClient,
        logger: AppLogger,
    ):
        self._rabbit = rabbit
        self._logger = logger
        self._stop_event = None

    async def start(self, stop: asyncio.Event):
        """Запуск consumer'а с возможностью остановки"""
        self._stop_event = stop
        await self.register_consumers()

        await self._stop_event.wait()

        self._logger.info("Stop signal received, cancelling consumers...")
        await self._rabbit.cancel_consumer()

    async def register_consumers(self) -> None:
        """Настройка всех consumers для обработки сообщений"""


        self._logger.info("Consumer started")

