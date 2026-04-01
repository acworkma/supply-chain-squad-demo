from .metrics_store import MetricsStore

__all__ = ["MetricsStore", "metrics_store"]

# Singleton instance used by routers and scenarios
metrics_store = MetricsStore()
