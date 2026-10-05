# Zurick lockin amplifier(HF2Server)

A TCP-based gateway for Zurich Instruments HF2 series lock-in amplifiers. This server allows remote clients to control hardware nodes and acquire averaged data via a simple Tab-Separated Protocol.

## 📡 Network Protocol

The server uses a **Tab-Separated Protocol** over TCP.

**Request Format:**
`command` + `\t` + `arg1` + `\t` + `arg2` ... + `\n`

**Response Format:**
* `1\t[Data]\n` : **Success**.
* `0\t[Error Message]\n` : **Failure**.

# HF2Server Reference

A TCP-based gateway for Zurich Instruments HF2 series lock-in amplifiers. This server allows remote clients to control hardware nodes and acquire averaged data via a simple Tab-Separated Protocol.

## 📡 Network Protocol

**Request Format:** `command` + `\t` + `arg1` + `\t` + `arg2` ... + `\n`
**Response Format:** `1\t[Data]\n` (Success) or `0\t[Error Message]\n` (Failure)

## 📖 Complete Command Reference

| Command | Arguments | Description |
| :--- | :--- | :--- |
| **Data Acquisition** | | |
| `get_data` | `duration` (float) | Returns: `x, y, theta, scope_mean, r` |
| `setup_scope` | `freq`, `len`, `ch` | Configures Scope for single shot (Time, Length, Input Select). |
| **Oscillator & Output** | | |
| `set_ref_freq` | `val` (float) | Sets Lockin reference Frequency (Hz). |
| `set_ref_v` | `val` (float) | Sets reference voltage Amplitude (Vpk). |
| `set_ref_voff` | `val` (float) | Sets Signal voltage Offset (V). |
| `set_ref_out`| `state` (0/1) | Enables (1) or Disables (0) Signal Output 0. |
| **Demodulator Settings** | | |
| `set_tc` | `val` (float) | Sets Lockin (low pass) Time Constant (s). |
| `set_datarate` | `val` (float) | Sets Demodulator 0 Sample Rate (Hz). |
| `set_ref_harm` | `val` (int) | Sets Demodulator Harmonic. |
| **Input & Autorange** | | |
| `set_curr_range`| `val` (float) | Sets Current Input Range (Powers of 10). |
| `auto_curr_range`| None | Triggers Autorange for Current Input 0. |
| `auto_v`| None | Triggers Autorange for Signal Input 0. |
| **System** | | |
| `ping` | None | Returns `1\t` if server is alive. |
| `connect_hardware`| None | Re-establishes connection to ZI Data Server. |
| `disconnect_hardware`| None | Safely disconnects from hardware. |
| `shutdown` | None | Stops the server and disconnects hardware. |
## 💻 Example Usage

### 1. Start the Server
```python
from sm_bluesky.common.servers import HF2Server

server = HF2Server(
    host="0.0.0.0", port=7891, device_id="dev4206", hf2_ip="172.23.110.84"
)
server.start()
```
### 2. Client

```python
import socket


def query_hf2(command):
    with socket.create_connection(("localhost", 7891)) as sock:
        sock.sendall(f"{command}\n".encode())
        return sock.recv(1024).decode()


# Example: Get 0.5s of averaged data
print(query_hf2("get_data\t0.5"))
```
