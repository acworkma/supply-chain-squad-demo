from .message_store import MessageStore

__all__ = ["MessageStore", "message_store"]

# Singleton instance used by routers and tools
message_store = MessageStore()
