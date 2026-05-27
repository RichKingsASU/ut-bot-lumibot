import time
import logging
from collections import defaultdict, deque
from typing import Dict

logger = logging.getLogger('CircuitBreaker')


class NodeCircuitBreaker:
    def __init__(self,
                 failure_threshold: int = 3,
                 recovery_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failures: Dict[str, deque] = defaultdict(deque)
        self.open_circuits: Dict[str, float] = {}

    def record_failure(self, node_name: str):
        now = time.time()
        self.failures[node_name].append(now)
        cutoff = now - self.recovery_seconds
        while (self.failures[node_name] and
               self.failures[node_name][0] < cutoff):
            self.failures[node_name].popleft()
        count = len(self.failures[node_name])
        if count >= self.failure_threshold:
            self.open_circuits[node_name] = now
            logger.warning(
                f'[CB] {node_name} circuit OPEN '
                f'after {count} failures'
            )

    def record_success(self, node_name: str):
        if node_name in self.failures:
            self.failures[node_name].clear()
        self.open_circuits.pop(node_name, None)

    def is_open(self, node_name: str) -> bool:
        if node_name not in self.open_circuits:
            return False
        elapsed = (time.time() -
                   self.open_circuits[node_name])
        if elapsed > self.recovery_seconds:
            del self.open_circuits[node_name]
            logger.info(
                f'[CB] {node_name} circuit CLOSED '
                f'after {elapsed:.0f}s'
            )
            return False
        return True

    def get_status(self) -> dict:
        return {
            'open_circuits': list(
                self.open_circuits.keys()),
            'failure_counts': {
                k: len(v)
                for k, v in self.failures.items()
                if v
            }
        }


CIRCUIT_BREAKER = NodeCircuitBreaker(
    failure_threshold=3,
    recovery_seconds=300
)
