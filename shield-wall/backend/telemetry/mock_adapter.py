import json
import os
from backend.telemetry.base import TelemetryAdapter

class MockTelemetryAdapter(TelemetryAdapter):
    def __init__(self):
        base_dir = "./data/mock_infra"
        self.data = {}
        files = {
            "cloudtrail": "cloudtrail_events.json",
            "iam": "iam_policies.json",
            "kms": "kms_keys.json",
            "rds": "rds_instances.json",
            "sg": "security_groups.json"
        }
        for k, v in files.items():
            try:
                with open(os.path.join(base_dir, v), "r") as f:
                    self.data[k] = json.load(f)
            except FileNotFoundError:
                self.data[k] = {}

    async def execute(self, function_name: str, **kwargs) -> dict | list:
        if function_name == "query_cloudtrail":
            events = self.data.get("cloudtrail", [])
            event_name = kwargs.get("event_name")
            if event_name:
                events = [e for e in events if e.get("eventName") == event_name]
            return events
            
        elif function_name == "query_iam_config":
            query_type = kwargs.get("query_type")
            return self.data.get("iam", {}).get(query_type, {})
            
        elif function_name == "query_encryption_status":
            resource_type = kwargs.get("resource_type")
            if resource_type == "rds":
                return self.data.get("rds", {})
            return self.data.get("kms", {})
            
        elif function_name == "query_network_config":
            return self.data.get("sg", {})
            
        return {"error": "Unknown function or missing data"}
