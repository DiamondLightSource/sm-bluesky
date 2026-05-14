# Instrument Server (AbstractInstrumentServer)

A TCP server framework designed for interfacing with scientific instruments. This base class handles the network management, socket lifecycles, and command buffering, allowing you to focus exclusively on hardware-specific logic.

## Features

* **Connection Lifecycle Management:** Automatic handling of client connections and disconnections via Python context managers.
* **Command Dispatcher:** Built-in registry for mapping byte-string commands (e.g., `b"move"`) to Python methods.
* **Buffered Parsing:** Correctly handles TCP fragmentation by buffering incoming data until a newline (`\n`) is reached.
* **Timeout Safety:** Includes a deadline-based timeout context to prevent hardware hangs from locking the server loop.
* **Standardized Logging:** Integrated with `sm_bluesky.log` for consistent tracking of server events and errors.

---

## Communication Protocol

The server communicates using a simple **Tab-Separated Value (TSV)** format over a raw TCP stream.

### Request Format (Client → Server)
Commands must be newline-terminated.
`COMMAND` + `\t` + `ARG1` + `\t` + `ARG2...` + `\n`

### Response Format (Server → Client)
* **Success:** `1` + `\t` + `[Optional Data]` + `\n`
* **Error:** `0` + `\t` + `[Error Message]` + `\n`

---

## Default Methods

| Command | Arguments | Description |
| :--- | :--- | :--- |
 |`ping` | None | Returns `1\t` if server is alive. |
| `connect_hardware`| None | Re-establishes connection to hardware server. |
| `disconnect_hardware`| None | Safely disconnects from hardware. |
| `shutdown` | None | Stops the server and disconnects hardware. |


## Implementation Guide

To use this framework, create a subclass and implement the mandatory abstract methods.

### 1. Define your Hardware Class
```python
from sm_bluesky.servers import AbstractInstrumentServer

class MyMotorServer(AbstractInstrumentServer):
    def __init__(self, host, port):
        super().__init__(host, port)
        # Add custom hardware commands to the registry
        self._command_registry[b"move_abs"] = self._move_absolute

    def connect_hardware(self) -> bool:
        # Logic to initialize your physical device
        print("Initializing Motor...")
        return True

    def disconnect_hardware(self) -> None:
        # Logic to safely shut down hardware
        print("Parking Motor...")

    def _move_absolute(self, position: bytes):
        # Hardware logic: convert bytes arg to float
        pos_mm = float(position)
        print(f"Moving to {pos_mm}mm")
        
        # Periodic timeout check for long operations
        self._check_timeout("Motor Move")
        
        self._send_response(b"Moved to " + position)
if __name__ == "__main__":
    # Initialize and start the server
    server = MyInstrumentServer("127.0.0.1", 5000)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
