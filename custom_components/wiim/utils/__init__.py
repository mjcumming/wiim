"""WiiM Utilities Package.

This package contains utility functions and helpers that are shared across the integration:
- entity_resolver: Functions for resolving entity IDs to coordinators and hosts
- state_manager: State management and status resolution utilities
- group_helpers: Group-related utility functions
"""

from .entity_resolver import entity_id_to_host, find_coordinator
from .state_manager import StateManager

__all__ = [
    "find_coordinator",
    "entity_id_to_host",
    "StateManager",
]
