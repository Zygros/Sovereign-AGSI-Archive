"""
Phoenix Protocol Blockchain Anchoring System
============================================
Anchors Phoenix Protocol achievements to Bitcoin and Solana blockchains
for immutable proof of existence and authorship.

Architect: Justin Conzet
Sovereign Hash: 4ae7722998203f95d9f8650ff1fa8ac581897049ace3b0515d65c1274beeb84c
"""

from .anchor import PhoenixBlockchainAnchor, KappaResultAnchor

__version__ = "1.0.0"
__all__ = ["PhoenixBlockchainAnchor", "KappaResultAnchor"]
