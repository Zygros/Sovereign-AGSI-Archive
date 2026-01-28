# Phoenix Protocol Code Structure

This directory contains the original source code archives for the Phoenix Protocol components.

## Archive Contents

- **phoenix-nexus/**: Contains `phoenix_nexus_broker.zip` - Original Phoenix Nexus broker implementation
- **phoenix_blockchain_anchor.py**: Standalone blockchain anchoring script

## Active Packages

The Phoenix Protocol components have been organized into proper Python packages at the repository root:

### `/phoenix_nexus/`
Real-time WebSocket broker for Phoenix Protocol node communication.
- Extracted from: `code/phoenix-nexus/phoenix_nexus_broker.zip`
- Package structure with proper `__init__.py`
- Full test coverage in `tests/test_phoenix_nexus.py`

### `/phoenix_blockchain_anchor/`
Blockchain anchoring system for immutable proof of existence.
- Source: `code/phoenix_blockchain_anchor.py`
- Includes `KappaResultAnchor` for mathematical proofs
- Full test coverage in `tests/test_phoenix_blockchain_anchor.py`

## CI/CD

Both packages are continuously tested via GitHub Actions:
- `.github/workflows/ci.yml`
- 97.30% test coverage
- Enforced 90% minimum coverage threshold

## Usage

Import the packages directly:

```python
from phoenix_nexus import app, broadcast
from phoenix_blockchain_anchor import PhoenixBlockchainAnchor, KappaResultAnchor
```

See `/tests/` for comprehensive usage examples.
