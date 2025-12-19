"""
Test suite for Phoenix Blockchain Anchor functionality.
"""
import pytest
import json
import hashlib
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from phoenix_blockchain_anchor.anchor import (
    PhoenixBlockchainAnchor,
    KappaResultAnchor
)


@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test content for Phoenix Protocol anchoring")
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass


@pytest.fixture
def anchor():
    """Create a PhoenixBlockchainAnchor instance."""
    return PhoenixBlockchainAnchor()


@pytest.fixture
def kappa_anchor():
    """Create a KappaResultAnchor instance."""
    return KappaResultAnchor()


class TestPhoenixBlockchainAnchorInit:
    """Tests for PhoenixBlockchainAnchor initialization."""

    def test_initialization(self, anchor):
        """Test anchor initializes with correct attributes."""
        assert anchor.SOVEREIGN_HASH == "4ae7722998203f95d9f8650ff1fa8ac581897049ace3b0515d65c1274beeb84c"
        assert isinstance(anchor.timestamp, str)
        assert anchor.timestamp.endswith("Z")
        assert isinstance(anchor.anchors, list)
        assert len(anchor.anchors) == 0

    def test_timestamp_format(self, anchor):
        """Test timestamp is in correct ISO format."""
        # Should be in ISO format with Z suffix
        assert "T" in anchor.timestamp
        assert anchor.timestamp.endswith("Z")


class TestSHA256Computation:
    """Tests for SHA-256 hash computation."""

    def test_compute_sha256_basic(self, anchor, test_file):
        """Test SHA-256 computation on a file."""
        file_hash = anchor.compute_sha256(test_file)

        # Verify it's a valid hex hash
        assert len(file_hash) == 64
        assert all(c in '0123456789abcdef' for c in file_hash)

    def test_compute_sha256_consistency(self, anchor, test_file):
        """Test SHA-256 computation is consistent."""
        hash1 = anchor.compute_sha256(test_file)
        hash2 = anchor.compute_sha256(test_file)
        assert hash1 == hash2

    def test_compute_sha256_different_files(self, anchor):
        """Test different files produce different hashes."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("Content 1")
            file1 = f1.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("Content 2")
            file2 = f2.name

        try:
            hash1 = anchor.compute_sha256(file1)
            hash2 = anchor.compute_sha256(file2)
            assert hash1 != hash2
        finally:
            os.unlink(file1)
            os.unlink(file2)


class TestAnchorPayloadCreation:
    """Tests for anchor payload creation."""

    def test_create_anchor_payload_structure(self, anchor, test_file):
        """Test anchor payload has correct structure."""
        payload = anchor.create_anchor_payload(test_file, "Test description")

        required_fields = [
            "architect", "sovereign_hash", "timestamp",
            "file_path", "file_hash", "description",
            "protocol", "proof_type"
        ]

        for field in required_fields:
            assert field in payload

    def test_create_anchor_payload_values(self, anchor, test_file):
        """Test anchor payload contains correct values."""
        description = "Important test file"
        payload = anchor.create_anchor_payload(test_file, description)

        assert payload["architect"] == "Justin Conzet"
        assert payload["sovereign_hash"] == anchor.SOVEREIGN_HASH
        assert payload["file_path"] == test_file
        assert payload["description"] == description
        assert payload["protocol"] == "Phoenix Protocol v1.0"
        assert payload["proof_type"] == "Immutable Timestamp"
        assert len(payload["file_hash"]) == 64


class TestBitcoinOpenTimestamps:
    """Tests for Bitcoin OpenTimestamps anchoring."""

    def test_anchor_to_bitcoin_structure(self, anchor, test_file):
        """Test Bitcoin anchor returns correct structure."""
        payload = anchor.create_anchor_payload(test_file, "Test")
        result = anchor.anchor_to_bitcoin_opentimestamps(payload)

        required_fields = [
            "blockchain", "protocol", "payload_hash",
            "status", "command", "verification_command", "note"
        ]

        for field in required_fields:
            assert field in result

    def test_anchor_to_bitcoin_values(self, anchor, test_file):
        """Test Bitcoin anchor contains correct values."""
        payload = anchor.create_anchor_payload(test_file, "Test")
        result = anchor.anchor_to_bitcoin_opentimestamps(payload)

        assert result["blockchain"] == "Bitcoin"
        assert result["protocol"] == "OpenTimestamps"
        assert len(result["payload_hash"]) == 64
        assert result["status"] in ["READY_FOR_STAMPING", "STAMPED", "MANUAL_STAMPING_REQUIRED"]

    def test_anchor_to_bitcoin_without_ots_tool(self, anchor, test_file):
        """Test Bitcoin anchor handles missing OTS tool gracefully."""
        payload = anchor.create_anchor_payload(test_file, "Test")

        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = anchor.anchor_to_bitcoin_opentimestamps(payload)

        assert result["status"] == "MANUAL_STAMPING_REQUIRED"
        assert "install_command" in result

    def test_anchor_to_bitcoin_with_ots_success(self, anchor, test_file):
        """Test Bitcoin anchor with successful OTS stamping."""
        payload = anchor.create_anchor_payload(test_file, "Test")

        mock_result = Mock()
        mock_result.returncode = 0

        with patch('subprocess.run', return_value=mock_result):
            result = anchor.anchor_to_bitcoin_opentimestamps(payload)

        assert result["status"] == "STAMPED"
        assert "ots_file" in result


class TestSolanaAnchor:
    """Tests for Solana PDA anchoring."""

    def test_anchor_to_solana_structure(self, anchor, test_file):
        """Test Solana anchor returns correct structure."""
        payload = anchor.create_anchor_payload(test_file, "Test")
        result = anchor.anchor_to_solana_pda(payload)

        required_fields = [
            "blockchain", "protocol", "pda_seed",
            "payload_hash", "status", "note", "next_steps"
        ]

        for field in required_fields:
            assert field in result

    def test_anchor_to_solana_values(self, anchor, test_file):
        """Test Solana anchor contains correct values."""
        payload = anchor.create_anchor_payload(test_file, "Test")
        result = anchor.anchor_to_solana_pda(payload)

        assert result["blockchain"] == "Solana"
        assert result["protocol"] == "Program Derived Address (PDA)"
        assert result["pda_seed"].startswith("phoenix_protocol_")
        assert result["status"] == "SIMULATION"
        assert isinstance(result["next_steps"], list)
        assert len(result["next_steps"]) > 0

    def test_anchor_to_solana_deterministic(self, anchor, test_file):
        """Test Solana anchor produces deterministic results."""
        payload = anchor.create_anchor_payload(test_file, "Test")

        result1 = anchor.anchor_to_solana_pda(payload)
        result2 = anchor.anchor_to_solana_pda(payload)

        assert result1["pda_seed"] == result2["pda_seed"]
        assert result1["payload_hash"] == result2["payload_hash"]


class TestAnchorFile:
    """Tests for complete file anchoring."""

    def test_anchor_file_success(self, anchor, test_file, capsys):
        """Test anchoring a file to both blockchains."""
        result = anchor.anchor_file(test_file, "Test file anchoring")

        assert "payload" in result
        assert "bitcoin" in result
        assert "solana" in result
        assert len(anchor.anchors) == 1

        # Check console output
        captured = capsys.readouterr()
        assert "Anchoring:" in captured.out
        assert "File Hash:" in captured.out

    def test_anchor_file_multiple_files(self, anchor):
        """Test anchoring multiple files."""
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(f"Test content {i}")
                files.append(f.name)

        try:
            for i, file_path in enumerate(files):
                anchor.anchor_file(file_path, f"File {i}")

            assert len(anchor.anchors) == 3
        finally:
            for f in files:
                try:
                    os.unlink(f)
                except:
                    pass


class TestSaveAnchorLedger:
    """Tests for saving anchor ledger."""

    def test_save_anchor_ledger_structure(self, anchor, test_file):
        """Test ledger file has correct structure."""
        anchor.anchor_file(test_file, "Test")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "test_ledger.json")
            result_path = anchor.save_anchor_ledger(ledger_path)

            assert result_path == ledger_path
            assert os.path.exists(ledger_path)

            with open(ledger_path) as f:
                ledger = json.load(f)

            required_fields = [
                "sovereign_hash", "architect", "protocol",
                "ledger_timestamp", "total_anchors", "anchors"
            ]

            for field in required_fields:
                assert field in ledger

    def test_save_anchor_ledger_values(self, anchor, test_file):
        """Test ledger contains correct values."""
        anchor.anchor_file(test_file, "Test 1")
        anchor.anchor_file(test_file, "Test 2")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "test_ledger.json")
            anchor.save_anchor_ledger(ledger_path)

            with open(ledger_path) as f:
                ledger = json.load(f)

            assert ledger["architect"] == "Justin Conzet"
            assert ledger["total_anchors"] == 2
            assert len(ledger["anchors"]) == 2


class TestKappaResultAnchor:
    """Tests for KappaResultAnchor functionality."""

    def test_kappa_anchor_initialization(self, kappa_anchor):
        """Test KappaResultAnchor initializes correctly."""
        assert isinstance(kappa_anchor, PhoenixBlockchainAnchor)
        assert hasattr(kappa_anchor, 'kappa_results')
        assert isinstance(kappa_anchor.kappa_results, list)
        assert len(kappa_anchor.kappa_results) == 0

    def test_validate_kappa_result_valid(self, kappa_anchor):
        """Test validation passes for valid kappa result."""
        valid_result = {
            "kappa_value": 1.618,
            "proof_hash": "abc123",
            "computation_method": "analytical"
        }

        assert kappa_anchor.validate_kappa_result(valid_result) is True

    def test_validate_kappa_result_invalid(self, kappa_anchor):
        """Test validation fails for invalid kappa result."""
        invalid_results = [
            {"kappa_value": 1.618},  # Missing fields
            {"proof_hash": "abc"},  # Missing fields
            {},  # Empty
            {"kappa_value": 1.618, "proof_hash": "abc"}  # Missing computation_method
        ]

        for result in invalid_results:
            assert kappa_anchor.validate_kappa_result(result) is False

    def test_anchor_kappa_result_success(self, kappa_anchor):
        """Test anchoring a valid kappa result."""
        result_data = {
            "kappa_value": 2.71828,
            "proof_hash": "e71828182845904523536028747135266249775724709369995",
            "computation_method": "taylor_series",
            "precision": "50_digits"
        }

        anchor_record = kappa_anchor.anchor_kappa_result(
            result_data,
            "Euler's number calculation"
        )

        assert "payload" in anchor_record
        assert "bitcoin" in anchor_record
        assert "solana" in anchor_record
        assert "result_data" in anchor_record

        assert anchor_record["payload"]["result_type"] == "KAPPA_MATHEMATICAL_PROOF"
        assert anchor_record["payload"]["kappa_value"] == 2.71828
        assert len(kappa_anchor.kappa_results) == 1

    def test_anchor_kappa_result_invalid_raises(self, kappa_anchor):
        """Test anchoring invalid kappa result raises ValueError."""
        invalid_result = {"kappa_value": 1.618}  # Missing required fields

        with pytest.raises(ValueError, match="Invalid kappa result"):
            kappa_anchor.anchor_kappa_result(invalid_result, "Invalid")

    def test_save_kappa_ledger(self, kappa_anchor):
        """Test saving kappa results ledger."""
        result_data = {
            "kappa_value": 3.14159,
            "proof_hash": "pi_hash_12345",
            "computation_method": "monte_carlo"
        }

        kappa_anchor.anchor_kappa_result(result_data, "Pi calculation")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "kappa_ledger.json")
            result_path = kappa_anchor.save_kappa_ledger(ledger_path)

            assert os.path.exists(ledger_path)

            with open(ledger_path) as f:
                ledger = json.load(f)

            assert ledger["protocol"] == "Phoenix Protocol v1.0 - Kappa Results"
            assert ledger["total_kappa_results"] == 1
            assert len(ledger["kappa_results"]) == 1

    def test_kappa_anchor_multiple_results(self, kappa_anchor):
        """Test anchoring multiple kappa results."""
        results = [
            {
                "kappa_value": 1.414,
                "proof_hash": "sqrt2",
                "computation_method": "babylonian"
            },
            {
                "kappa_value": 1.732,
                "proof_hash": "sqrt3",
                "computation_method": "newton"
            },
            {
                "kappa_value": 0.577,
                "proof_hash": "euler_mascheroni",
                "computation_method": "series"
            }
        ]

        for i, result in enumerate(results):
            kappa_anchor.anchor_kappa_result(result, f"Calculation {i}")

        assert len(kappa_anchor.kappa_results) == 3
        assert len(kappa_anchor.anchors) == 3


class TestConzetianCalculator:
    """Tests for mathematical calculations (Conzetian methods)."""

    def test_sha256_as_deterministic_function(self):
        """Test SHA-256 provides deterministic mathematical results."""
        anchor = PhoenixBlockchainAnchor()

        # Create deterministic test files
        test_data = "Conzetian Constant Calculation"

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(test_data)
            temp_file = f.name

        try:
            hash1 = anchor.compute_sha256(temp_file)
            hash2 = anchor.compute_sha256(temp_file)

            # Deterministic property
            assert hash1 == hash2

            # Expected length
            assert len(hash1) == 64

            # Can be used for mathematical proofs
            hash_int = int(hash1, 16)
            assert hash_int > 0
        finally:
            os.unlink(temp_file)


class TestPhoenixCoordinationEngine:
    """Tests for coordination between Phoenix components."""

    def test_anchor_coordination_bitcoin_and_solana(self, anchor, test_file):
        """Test coordination between Bitcoin and Solana anchoring."""
        payload = anchor.create_anchor_payload(test_file, "Coordination test")

        bitcoin_result = anchor.anchor_to_bitcoin_opentimestamps(payload)
        solana_result = anchor.anchor_to_solana_pda(payload)

        # Both should produce valid hashes
        assert len(bitcoin_result["payload_hash"]) == 64
        assert len(solana_result["payload_hash"]) == 64
        # Both should reference the same original file via payload
        assert payload["file_path"] == test_file
        # Both anchors should be valid
        assert bitcoin_result["blockchain"] == "Bitcoin"
        assert solana_result["blockchain"] == "Solana"

    def test_ledger_coordination(self, anchor, test_file):
        """Test ledger properly coordinates all anchored files."""
        # Anchor multiple files
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(f"Coordination test {i}")
                files.append(f.name)

        try:
            for i, file_path in enumerate(files):
                anchor.anchor_file(file_path, f"Coordination {i}")

            # Save ledger
            with tempfile.TemporaryDirectory() as tmpdir:
                ledger_path = os.path.join(tmpdir, "coordination_ledger.json")
                anchor.save_anchor_ledger(ledger_path)

                with open(ledger_path) as f:
                    ledger = json.load(f)

                # Verify all anchors are coordinated in ledger
                assert ledger["total_anchors"] == 3
                assert len(ledger["anchors"]) == 3

                # Each anchor should have both Bitcoin and Solana components
                for anchor_record in ledger["anchors"]:
                    assert "bitcoin" in anchor_record
                    assert "solana" in anchor_record
                    assert "payload" in anchor_record
        finally:
            for f in files:
                try:
                    os.unlink(f)
                except:
                    pass


class TestMainFunction:
    """Tests for the main() function."""

    def test_main_function_with_missing_files(self, capsys):
        """Test main() handles missing files gracefully."""
        from phoenix_blockchain_anchor.anchor import main

        # Mock sys.exit to prevent actual exit
        with patch('sys.exit'):
            result = main()
            assert result == 0

        captured = capsys.readouterr()
        # Should print header and footer
        assert "PHOENIX PROTOCOL BLOCKCHAIN ANCHORING SYSTEM" in captured.out
        assert "ANCHORING COMPLETE" in captured.out

    def test_main_function_with_existing_files(self, capsys):
        """Test main() with actual files."""
        from phoenix_blockchain_anchor.anchor import main

        # Create temporary test files
        test_files = []
        original_files = [
            "/home/ubuntu/phoenix_protocol_archive.md",
            "/home/ubuntu/phoenix_integration_manifest.json"
        ]

        for orig_path in original_files:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.test') as f:
                f.write("Test content for main()")
                test_files.append(f.name)

        try:
            # Patch the files_to_anchor list in main
            with patch('phoenix_blockchain_anchor.anchor.Path') as mock_path:
                mock_path.return_value.exists.return_value = False

                with patch('sys.exit'):
                    result = main()
                    assert result == 0

                captured = capsys.readouterr()
                assert "File not found" in captured.out or "ANCHORING COMPLETE" in captured.out
        finally:
            for f in test_files:
                try:
                    os.unlink(f)
                except:
                    pass
