# ACIT Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/jdu-acit/ACIT_HA_Integration.svg)](https://github.com/jdu-acit/ACIT_HA_Integration/releases)
[![License](https://img.shields.io/github/license/jdu-acit/ACIT_HA_Integration.svg)](LICENSE)

Home Assistant custom integration for ACIT electronic boards - Smart temperature and setpoint management.

**Supported Models:**

The integration identifies a device from the model it announces itself (mDNS TXT
record `model=`, `Thermostat.GetConfig`), and only exposes the entities that
model actually has.

| Announced `model` | Product | Entities |
| --- | --- | --- |
| `ACCU_ThermACEC` | 🌡️ **ACCU-ThermACEC** — heat-storage radiator | temperature, setpoint, heating, fan, core charge |
| `NOS_ThermACEC` | 🌡️ **NOS-ThermACEC** — two-stage convector | temperature, setpoint, heating |
| `A2_ThermACEC` | 🌡️ **A2-ThermACEC** — KC868-A2 controller (2 relays, RS485, 4G) | temperature, setpoint, heating |
| `AccuBloc_ThermACEC` | 🔋 **AccuBloc-ThermACEC** *(coming soon)* — industrial heat storage | temperature, setpoint, heating, cooling, fan |
| `EMS_ThermACEC` | ⚡ **EMS-ThermACEC** *(coming soon)* — energy manager | power, energy import/export, relays |

An unrecognized model gets a minimal profile (temperature and setpoint only) and
a warning in the log, rather than the entities of another product.

## 🌟 Features

- 🌡️ **Ambient temperature sensor** - Real-time reading
- 🎯 **Temperature setpoint control** - Complete climate entity
- 🚀 **HTTP RPC API** - JSON-RPC 2.0 protocol for commands
- 📡 **WebSocket notifications** - Real-time push updates
- 🔍 **mDNS auto-discovery** - Automatic device detection via Zeroconf
- 🌐 **Multi-language interface** - Complete translations (FR/EN)
- ⚙️ **UI configuration** - No manual YAML editing
- 🏠 **Local control** - Direct communication, no cloud or broker required

## 📋 Prerequisites

- Home Assistant 2024.1.0 or higher
- ACIT electronic board (ACCU, NOS, A2, etc.) with firmware v2.0+
- Local network connectivity (device and Home Assistant on same network)

## 📦 Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click on the ⋮ menu in the top right
4. Select "Custom repositories"
5. Add the URL: `https://github.com/jdu-acit/ACIT_HA_Integration`
6. Select category "Integration"
7. Click on "ACIT" in the list
8. Click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest version from [Releases](https://github.com/jdu-acit/ACIT_HA_Integration/releases)
2. Copy the `custom_components/acit` folder to your `config/custom_components/` directory
3. Restart Home Assistant

## ⚙️ Configuration

### Option 1: Automatic Discovery (Recommended)

1. Power on your ACIT device
2. Go to **Settings** → **Devices & Services**
3. The device should appear automatically in **Discovered** section
4. Click **Configure** and confirm the device

### Option 2: Manual Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **ACIT**
4. Enter the device information:
   - **Device Name**: Custom name for your device
   - **IP Address**: Device IP (e.g., `10.0.0.41`)
   - **Port**: HTTP port (default: `80`)

## 🔌 Architecture

### HTTP RPC API

The integration uses JSON-RPC 2.0 protocol over HTTP for commands:

**Endpoint**: `http://<device-ip>/rpc`

**Available Methods**:
- `Thermostat.GetStatus` - Get current temperature, setpoint, heater level, fan speed
- `Thermostat.GetConfig` - Get device configuration (model, version, MAC address, limits)
- `Thermostat.SetTargetTemp` - Set temperature setpoint

**Example Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "Thermostat.SetTargetTemp",
  "params": {
    "temperature": 22.5
  }
}
```

### WebSocket Notifications

Real-time updates are pushed via WebSocket:

**Endpoint**: `ws://<device-ip>/ws`

**Notification Format**:
```json
{
  "jsonrpc": "2.0",
  "method": "NotifyStatus",
  "params": {
    "temperature": 21.8,
    "target_temperature": 22.0,
    "heater_level": 0,
    "fan_speed": 1
  }
}
```

### mDNS Discovery

Devices advertise themselves via mDNS:
- **Service Type**: `_acit._tcp.local.`
- **Hostname Pattern**: `acit-thermacec-<MAC>.local`

## 📊 Created Entities

### Temperature Sensor
- **Type**: `sensor`
- **Class**: `temperature`
- **Unit**: °C
- **Update**: Real-time via WebSocket notifications

### Thermostat (Climate Entity)
- **Type**: `climate`
- **Mode**: Heat (automatic control by device)
- **Temperature Range**: 5°C - 35°C (configurable on device)
- **Precision**: 0.1°C
- **Extra Attributes**:
  - `heater_level`: Current heating level (0-100)
  - `fan_speed`: Current fan speed (0-3)

## 🐛 Troubleshooting

### Integration doesn't appear

1. Verify the folder is in `custom_components/acit`
2. Restart Home Assistant
3. Clear your browser cache (Ctrl+F5)

### Device not discovered automatically

1. Verify the device is powered on and connected to the network
2. Check that Home Assistant and the device are on the same network/VLAN
3. Verify mDNS/Zeroconf is not blocked by your firewall
4. Try manual configuration with the device IP address

### Cannot connect to device

1. Verify the device IP address is correct
2. Test HTTP connection: `curl http://<device-ip>/rpc`
3. Check firewall rules (port 80 must be accessible)
4. Check logs: **Settings** → **System** → **Logs**

### No real-time updates

1. Verify WebSocket connection in logs
2. Check that port 80 is not blocked for WebSocket upgrade
3. The integration will fall back to polling if WebSocket fails

### Detailed Logs

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.acit: debug
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest features
- Submit pull requests

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**ACIT** - [jdu-acit](https://github.com/jdu-acit)

