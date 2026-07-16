# 📟sm-bluesky CLI Reference

The `sm-bluesky` command-line interface provides tools to launch instrument servers and interact with running instances via quick payloads (commands).

---

## 🚀 Commands Overview

The interface is split into two primary modes:
* **`start`**: Configures and spins up background hardware device server.
* **`send`**: A lightweight diagnostic utility to send arbitrary string payloads to an active server.

For extra information use:
* **`-h`, `--help`**: Displays general or command-specific help menus.
* **`-v`, `--version`**: Displays the currently installed package version of `sm-bluesky`.
---

## 🛠️ Detailed Usage

### 1. Starting an Instrument Server
Launches a dedicated hardware communication server. By default, it listens on all available interfaces (`0.0.0.0`) to ensure remote beamline workstations can reach the server.

```bash
sm-bluesky start sh_pulse_generator [FLAGS]
```
| Flag   | Type | Default | Description| 
| -----  | -----| ------  | -----------| 
| --host | str  | 0.0.0.0 | Binding host network address.| 
| --port | int | 7891 | TCP port boundary for socket listening. | 
| --ipv6 | bool | None | Flags the socket to use IPv6 dual-stack addressing. | 

### sh_pulse_generator Specific FlAG

| Flag   | Type | Default | Description| 
| -----  | -----| ------  | -----------| 
| --usb-port | str | COM4 | Target serial/USB backend port identifier. | 
| --baud-rate | int | 9600 | Serial connection baud rate. | 
| --timeout | float | 1.0 | Read/write timeout duration in seconds. | 
| --max-pulse-delay | int | 1024 | Boundary constraints for safe pulse adjustments. | 
```bash
sm-bluesky start sh_pulse_generator --usb-port COM9 --port 8080
```

### 2. Sending Payloads (Commands)

Sends a single string payload directly to an active server. It defaults to the local loopback address (127.0.0.1) to ensure accidental commands don't interact with external instruments.
```bash
sm-bluesky send "PAYLOAD" [FLAGS]
```

| Flag | Type | Default | Description | 
| -----| -----| ------  | -----------| 
| --host | str | 127.0.0.1 | Target server network address.| 
| --port | int | 7891 | Target server TCP communications port.| 
| --timeout | float | 2.0 | Connection timeout duration in seconds.| 

```bash
# Verify status locally
sm-bluesky send "command_list"

# Adjust settings on a remote beamline server
sm-bluesky send "SET_DELAY 512" --host 192.168.1.50 --port 7891```
