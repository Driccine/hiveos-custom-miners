"""Tests de conformité pour le prototype PoW ORU RGRPOW01."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from rgrpow import digest_header, meets_target, scan_nonces


class PowTests(unittest.TestCase):
    def test_zero_header_vector(self):
        self.assertEqual(
            digest_header(bytes(80)).hex(),
            "dd057fc1df8f5b9466e834cc9d7b819e2d511c75b43675b577f6d9f5d6de04fc",
        )

    def test_nonce_one_vector(self):
        header = bytes(76) + (1).to_bytes(4, "little")
        self.assertEqual(
            digest_header(header).hex(),
            "fd41791432e2aadbe17e3728d7c5d70f42432e2d30d44251aeffb76271bc71e4",
        )

    def test_reject_wrong_header(self):
        with self.assertRaises(ValueError):
            digest_header(bytes(79))

    def test_target_endianness(self):
        digest = digest_header(bytes(80))
        self.assertTrue(meets_target(digest, "ff" * 32))
        self.assertFalse(meets_target(digest, "00" * 32))

    def test_nonce_scan(self):
        result = scan_nonces(bytes(80), "ff" * 32, 1, 100)
        self.assertIsNotNone(result)
        self.assertEqual(result.nonce, 1)
        self.assertEqual(result.digest, digest_header(bytes(76) + b"\x01\x00\x00\x00"))


if __name__ == "__main__":
    unittest.main()
