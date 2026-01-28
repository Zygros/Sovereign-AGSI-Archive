"""
Phoenix Nexus - Real-time Communication Hub
============================================
Central broker for Phoenix Protocol node communication.

Architect: Justin Conzet
Sovereign Hash: 4ae7722998203f95d9f8650ff1fa8ac581897049ace3b0515d65c1274beeb84c
"""

from .nexus_broker import app, broadcast, clients

__version__ = "1.0.0"
__all__ = ["app", "broadcast", "clients"]
