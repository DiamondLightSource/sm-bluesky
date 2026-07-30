# Pulse Generator Server (ShanghaiTech)

A TCP/IP instrument server designed to control Pulse Generators via USB Serial (RS232).

## 1. Connection Specifications

| Parameter | Default Value |
| :--- | :--- |
| **Host** | `localhost` (127.0.0.1) |
| **TCP Port** | `8888` |
| **Interface** | USB Serial (COM / /dev/tty) |
| **Baud Rate** | `9600` |
| **Data Protocol** | Tab-Separated, Newline-Terminated (`\t`, `\n`) |

---

## 2. Communication Protocol



The server follows a **Request-Response** model. Every command sent by a client will receive a response starting with a status bit.

### Request Format
`COMMAND` + `\t` (Tab) + `ARGUMENT` (Optional) + `\n` (Newline)

### Response Format
* **Success:** `1` + `\t` + `Data/Message` + `\n`
* **Error:** `0` + `\t` + `Error Description` + `\n`

---

## 3. Command Registry

| Command | Argument | Description | Example |
| :--- | :--- | :--- | :--- |
| `ping` | None | Heartbeat check to verify server status. | `ping\n` |
| `connect_hardware` | None | Initializes/Re-opens the Serial port. | `connect_hardware\n` |
| `set_delay` | `0-1023` | Sets the pulse delay on the hardware. | `set_delay\t512\n` |
| `get_delay` | None | Queries the current delay from hardware. | `get_delay\n` |
| `reset_serial_buffer`| None | Clears the hardware's internal I/O buffers. | `reset_serial_buffer\n` |
| `pass_command` | `string` | Sends a raw AT command to the device. | `pass_command\tAT+VER\n` |
| `shutdown` | None | Safely stops the server and releases hardware. | `shutdown\n` |

---


## 4. Quick Start: Python Client

You can interact with the server using any language that supports sockets. Here is a minimal Python example:

```python
import socket

def send_pulse_command(ip, port, cmd, arg=None):
    try:
        with socket.create_connection((ip, port), timeout=2.0) as s:
            message = f"{cmd}\t{arg}\n" if arg else f"{cmd}\n"
            s.sendall(message.encode())
            response = s.recv(1024).decode().strip()
            
            status, data = response.split('\t', 1)
            if status == '1':
                print(f"SUCCESS: {data}")
            else:
                print(f"ERROR: {data}")
    except Exception as e:
        print(f"Connection Failed: {e}")

# Example Usage
send_pulse_command("127.0.0.1", 8888, "set_delay", "250")
