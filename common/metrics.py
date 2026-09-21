from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server


class WorkerAMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.published_messages = Counter(
            "dadekavan_worker_a_published_messages_total",
            "Total market-data messages published by WorkerA.",
            registry=self.registry,
        )
        self.fetch_failures = Counter(
            "dadekavan_worker_a_fetch_failures_total",
            "Total TSETMC fetch failures handled by WorkerA.",
            registry=self.registry,
        )
        self.redis_publish_errors = Counter(
            "dadekavan_worker_a_redis_publish_errors_total",
            "Total Redis publish failures handled by WorkerA.",
            registry=self.registry,
        )
        self.resolved_instruments = Gauge(
            "dadekavan_worker_a_resolved_instruments",
            "Number of TSETMC instruments resolved by WorkerA.",
            registry=self.registry,
        )
        self.batch_size = Gauge(
            "dadekavan_worker_a_last_batch_size",
            "Number of market-data messages in the latest WorkerA batch.",
            registry=self.registry,
        )
        self.last_publish_unixtime = Gauge(
            "dadekavan_worker_a_last_publish_unixtime",
            "Unix timestamp of the latest successful WorkerA Redis publish.",
            registry=self.registry,
        )
        self.cycle_duration_seconds = Histogram(
            "dadekavan_worker_a_cycle_duration_seconds",
            "WorkerA polling-cycle duration in seconds.",
            buckets=(0.05, 0.1, 0.2, 0.35, 0.5, 1.0, 2.0, 5.0, 10.0),
            registry=self.registry,
        )

    def start(self, port: int = 9101) -> None:
        start_http_server(port, addr="0.0.0.0", registry=self.registry)


class WorkerBMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.processed_messages = Counter(
            "dadekavan_worker_b_processed_messages_total",
            "Total Redis Stream messages successfully processed and acknowledged by WorkerB.",
            registry=self.registry,
        )
        self.failed_messages = Counter(
            "dadekavan_worker_b_failed_messages_total",
            "Total WorkerB message-processing attempts that failed.",
            registry=self.registry,
        )
        self.loop_errors = Counter(
            "dadekavan_worker_b_loop_errors_total",
            "Total WorkerB Redis/SQL loop errors.",
            registry=self.registry,
        )
        self.last_batch_size = Gauge(
            "dadekavan_worker_b_last_batch_size",
            "Number of messages successfully processed in the latest WorkerB read.",
            registry=self.registry,
        )
        self.last_success_unixtime = Gauge(
            "dadekavan_worker_b_last_success_unixtime",
            "Unix timestamp of the latest successfully acknowledged WorkerB message.",
            registry=self.registry,
        )

    def start(self, port: int = 9102) -> None:
        start_http_server(port, addr="0.0.0.0", registry=self.registry)
