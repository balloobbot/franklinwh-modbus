import os
import json
import pytest

class TestSequenceValidity:
    """Validates the syntax and structural soundness of all new sequencer JSON configurations."""

    SEQUENCER_DIR = "examples/sequencer"

    @pytest.fixture
    def sequence_files(self):
        """Finds all JSON files in the sequencer examples folder."""
        files = [
            f for f in os.listdir(self.SEQUENCER_DIR)
            if f.endswith(".json") and f not in [
                "basic_charge_release.json",
                "conflict_scenarios.json",
                "conflict_test_160.json",
                "exhaustive_demo.json",
                "extension_probe.json",
                "live_smoke_test.json",
                "roadmap_conformance.json",
                "wait_for_soc.json"
            ]
        ]
        return [os.path.join(self.SEQUENCER_DIR, f) for f in files]

    def test_json_loadability(self, sequence_files):
        """Verifies that every created sequence file is valid JSON and parses as a list of steps."""
        assert len(sequence_files) >= 12, f"Expected at least 12 new sequence files, found {len(sequence_files)}"
        
        for file_path in sequence_files:
            with open(file_path, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"File '{file_path}' failed JSON decoding: {e}")
                
                assert isinstance(data, list), f"Sequence in '{file_path}' must be a JSON array"
                assert len(data) > 0, f"Sequence in '{file_path}' cannot be empty"

    def test_step_attributes_and_logic(self, sequence_files):
        """Ensures sequencer steps follow the schema definition (contains naming, writes, wait_for, sleeps)."""
        valid_operators = ["==", "!=", ">", "<", ">=", "<=", "in", "not in"]
        
        for file_path in sequence_files:
            with open(file_path, "r") as f:
                steps = json.load(f)
                
            for idx, step in enumerate(steps):
                assert isinstance(step, dict), f"Step {idx} in '{file_path}' must be a dictionary"
                
                # Must have descriptive labeling
                has_name = "name" in step or "step" in step
                assert has_name, f"Step {idx} in '{file_path}' must contain 'step' or 'name' label"
                
                # Check write keys and verify values
                if "writes" in step:
                    writes = step["writes"]
                    assert isinstance(writes, dict), f"'writes' in step {idx} in '{file_path}' must be a dictionary"
                    assert len(writes) > 0, f"'writes' in step {idx} in '{file_path}' cannot be empty"
                    
                    for key, val in writes.items():
                        assert isinstance(key, str), f"Write key in step {idx} in '{file_path}' must be a string"
                        # Keys should be either Model.Point (e.g. 704.WSet) or register integer
                        if "." in key:
                            parts = key.split(".")
                            assert len(parts) == 2, f"Invalid point tag '{key}' in step {idx} in '{file_path}'"
                            assert parts[0].isdigit(), f"Model ID must be numeric in tag '{key}'"
                        else:
                            assert key.isdigit(), f"Raw write register must be numeric in '{key}'"
                
                # Check wait_for keys
                if "wait_for" in step:
                    wait_for = step["wait_for"]
                    assert isinstance(wait_for, dict), f"'wait_for' in step {idx} in '{file_path}' must be a dictionary"
                    assert "point" in wait_for, f"'wait_for' in step {idx} in '{file_path}' is missing 'point'"
                    
                    if "operator" in wait_for:
                        assert wait_for["operator"] in valid_operators, \
                            f"Unsupported operator '{wait_for['operator']}' in step {idx} in '{file_path}'"
                            
                    # Prevent second-based timeouts from being passed as millisecond-based config
                    if "timeout" in wait_for:
                        pytest.fail(f"Step {idx} in '{file_path}' uses second-based 'timeout' in wait_for. Use 'timeout_ms' instead.")
                    if "interval" in wait_for:
                        pytest.fail(f"Step {idx} in '{file_path}' uses second-based 'interval' in wait_for. Use 'poll_ms' instead.")

                # Ensure sleep keys are numeric and millisecond-based
                if "sleep_ms" in step:
                    assert isinstance(step["sleep_ms"], (int, float)), f"sleep_ms must be numeric in step {idx} in '{file_path}'"
                    assert step["sleep_ms"] >= 0, f"sleep_ms must be non-negative in step {idx} in '{file_path}'"
                if "post_sleep_ms" in step:
                    assert isinstance(step["post_sleep_ms"], (int, float)), f"post_sleep_ms must be numeric in step {idx} in '{file_path}'"
