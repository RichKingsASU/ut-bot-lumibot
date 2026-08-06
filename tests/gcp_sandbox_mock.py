import json

class SandboxException(Exception):
    pass

class MockPublisherClient:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.published_messages = []

    def topic_path(self, project, topic):
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic_path, data, ordering_key=None):
        if self.sandbox.simulate_500:
            raise SandboxException("500 Internal Server Error (PubSub)")
        if self.sandbox.simulate_429:
            raise SandboxException("429 Too Many Requests (PubSub)")
            
        # Safely ingest payloads and assert Pydantic-like schema structure
        payload = json.loads(data.decode('utf-8'))
        if "id" not in payload or "created_at" not in payload:
            raise SandboxException("Schema validation failed: missing id or created_at")
            
        self.published_messages.append({
            "topic": topic_path,
            "data": payload,
            "ordering_key": ordering_key
        })

class MockBigQueryClient:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.inserted_rows = []
        self.seen_insert_ids = set()

    def insert_rows_json(self, table_id, json_rows):
        if self.sandbox.simulate_500:
            raise SandboxException("500 Internal Server Error (BigQuery)")
            
        errors = []
        for row in json_rows:
            insert_id = row.get("insertId")
            
            if (table_id, insert_id) in self.seen_insert_ids:
                # Downstream deduplication: simulate discarding duplicate insert_ids silently
                continue
            
            self.seen_insert_ids.add((table_id, insert_id))
            self.inserted_rows.append({
                "table_id": table_id,
                "row": row["json"]
            })
            
        return errors # empty list means success

class GCPSandbox:
    """Local GCP test sandbox to test I/O boundaries offline."""
    def __init__(self):
        self.simulate_500 = False
        self.simulate_429 = False
        self.publisher = MockPublisherClient(self)
        self.bq_client = MockBigQueryClient(self)
        
    def reset(self):
        self.simulate_500 = False
        self.simulate_429 = False
        self.publisher.published_messages.clear()
        self.bq_client.inserted_rows.clear()
        self.bq_client.seen_insert_ids.clear()
