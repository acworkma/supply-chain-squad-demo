from .event_store import EventStore

__all__ = ["EventStore", "event_store"]

# Singleton instance used by routers and tools
event_store = EventStore()
