"""
Hardware tests for FranklinWH Battery Control.

These tests require an actual aGate device on the network.
They are marked with 'hardware' and skipped by default.

To run hardware tests:
    pytest -m hardware

To include destructive tests (writes to battery):
    pytest -m "hardware and destructive" --destructive-enabled
"""
