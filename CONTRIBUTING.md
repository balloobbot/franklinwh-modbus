# Contributing to franklinwh-modbus

Thank you for your interest in contributing! This project provides Modbus TCP control for FranklinWH battery storage systems and benefits greatly from community contributions.

## Getting Started

### Prerequisites

- Python 3.10+
- A FranklinWH aGate gateway on your LAN (for hardware testing)
- Git

### Development Setup

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Unit tests (no hardware required)
python3 -m pytest tests/unit/ -v

# Integration tests (no hardware required)
python3 -m pytest tests/integration/ -v

# Hardware tests (requires aGate on LAN)
python3 -m pytest tests/hardware/ -v --ip YOUR_AGATE_IP
```

## How to Contribute

### Reporting Bugs

- Use the [Bug Report](https://github.com/david2069/franklinwh-modbus/issues/new?template=bug_report.md) template
- Include your aGate firmware version (`--status` output shows this)
- Include the exact command and full error output
- Note whether you have **SPAN Modbus** unlock enabled

### Suggesting Features

- Use the [Feature Request](https://github.com/david2069/franklinwh-modbus/issues/new?template=feature_request.md) template
- Describe the use case and expected behavior

### Pull Requests

1. Fork the repo and create your branch from `develop`
2. Add or update tests for any new functionality
3. Ensure all tests pass: `python3 -m pytest tests/ -v`
4. Update documentation if you change public APIs
5. Submit a PR with a clear description of the change

### Code Style

- Follow PEP 8 for Python code
- Use type hints where practical
- Add docstrings to public methods
- Keep log messages informative but concise

### Hardware Testing

Many features interact with real hardware. If you don't have an aGate:

- Unit tests with mocks cover most logic
- Clearly mark hardware-dependent changes in your PR
- A maintainer with hardware will validate before merging

## Project Structure

```
src/franklinwh_modbus/     # Core library (the pip package)
tools/                     # CLI tools and utilities
tests/unit/                # Unit tests (mocked, no hardware)
tests/integration/         # Integration tests
tests/hardware/            # Live hardware tests
docs/                      # Documentation
schedules/                 # TOU schedule examples
```

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
