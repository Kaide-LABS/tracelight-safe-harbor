from backend.telemetry.base import TelemetryAdapter

class AWSLiveTelemetryAdapter(TelemetryAdapter):
    def __init__(self, session, database: str):
        self.session = session
        self.database = database
        
    async def execute(self, function_name: str, **kwargs) -> dict | list:
        raise NotImplementedError("Production adapter — requires AWS credentials")
