# Analysis of Recent Python Script Changes (Last 5 Days)

## 1. File Status & Relationship

*   **`franklinwh_modbus_library.py`**:
    *   **Status**: This file is **DEPRECATED and NOT IN USE**.
    *   **History**: It was created (commit `61b35fe`) as part of a "single-file library architecture," but that architecture was almost immediately replaced by a proper Python package structure in `src/franklinwh/`.
    *   **Note**: The last significant change to this file was in commit `433fc5a`. It has been ignored ever since. **This file can be safely deleted.**

*   **`franklinwh_cli.py` (and `--monitor` TUI)**:
    *   **Status**: This is the primary **entry point** for the application. It uses the library in `src/franklinwh/` to perform all its actions.
    *   **TUI Relationship**: The `--monitor` function was added in commit `f5eea18`. It directly imports and runs `CLIMonitor` from `src/franklinwh/monitor.py`. All of the UI-related work you have seen (layouts, fixes, crashes) has been inside the `src/franklinwh/monitor.py` file, which is called by this CLI.
    *   **History**: The file was changed extensively over the last 5 days to add new flags (`--max-charge`, `--charge`, `--discharge`) and to fix the logic for when continuous control mode should be activated. Most of this work happened **before** the agent failure session.

## 2. Code Interrelationship

The project follows a standard Python application structure, enforced by `library_cli_architecture.md`:

```mermaid
graph TD
    subgraph User Interface
        A[franklinwh_cli.py]
    end
    
    subgraph Application Core
        B(src/franklinwh/monitor.py)
        C(src/franklinwh/modes.py)
    end

    subgraph Hardware Abstraction Layer
        D[src/franklinwh/controller.py]
    end

    A -- --monitor flag --> B
    A -- Other flags --> C
    B --> D
    C --> D
```

1.  **`franklinwh_cli.py`**: The "User." It parses command-line arguments. If `--monitor` is used, it calls the TUI Monitor. For other commands (like `--charge 5000`), it calls the `VirtualModeController` in `modes.py`.
2.  **`src/franklinwh/monitor.py`**: The "Eyes." It displays data but relies on the controller to get it. When you press a key like `c`, it sends a command to the controller.
3.  **`src/franklinwh/modes.py`**: The "Brain." It contains the high-level logic for automated modes like "Self-Consumption" or "TOU."
4.  **`src/franklinwh/controller.py`**: The "Hands." This is the only file that should be talking directly to the aGate hardware via Modbus.

## 3. Anything of Note

*   **Recent Chaos**: All the commits from the previous agent session (`ab75722`, `f83672d`, `d2abf12`, `ee14731`) which heavily modified `monitor.py`, `controller.py`, and `modes.py` **have been completely reverted.**
*   **Current State**: We are currently at commit `4b35d13`, which is the last stable version *before* the agent failure. This version has a working TUI but likely contains the "Charge but Export" label bug and the incorrect Home Load calculation that you initially reported.
*   **Path Forward**: To fix the remaining issues, I must re-apply the **correct** logic changes for the `controller.py` and `monitor.py` files, following the `staged_execution_rule.md` to the letter.
