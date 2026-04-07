from abc import ABC, abstractmethod

class TelemetryAdapter(ABC):
    @abstractmethod
    async def execute(self, function_name: str, **kwargs) -> dict | list:
        """Execute a telemetry query and return the raw result."""
        pass
