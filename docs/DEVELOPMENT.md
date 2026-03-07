# Development & Safety Guidelines

## 🚨 CRITICAL SAFETY RULES 🚨

### 1. System Python Protection
**NEVER** make changes to the global system Python installation.
-   **DO NOT** run `pip install` with `sudo` or as root (unless explicitly in a container build script).
-   **DO NOT** modify `/usr/lib/python*` or `/usr/local/lib/python*`.
-   **ALWAYS** use a virtual environment (`venv`) for dependencies.

### 2. Dependency Management
-   All project dependencies must be listed in `requirements.txt`.
-   Install dependencies ONLY into the local virtual environment:
    ```bash
    # Correct way
    source venv/bin/activate
    pip install package_name
    ```

## Development Setup

1.  **Create Virtual Environment**:
    ```bash
    python3 -m venv venv
    ```

2.  **Activate Environment**:
    ```bash
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run Application**:
    ```bash
    ./run.sh
    ```
