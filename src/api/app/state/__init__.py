from .store import StateStore

__all__ = ["StateStore", "store"]

# Singleton instance used by routers and tools
store = StateStore()
