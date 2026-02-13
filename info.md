# ACIT Home Assistant Integration

Home Assistant custom integration for ACIT electronic boards - Smart temperature and setpoint management with support for multiple product models.

## 🌟 Key Features

- **🌡️ Temperature Sensor** - Real-time ambient temperature reading
- **🎯 Setpoint Control** - Complete climate entity with temperature control
- **🚀 HTTP RPC API** - JSON-RPC 2.0 protocol for commands
- **� WebSocket Notifications** - Real-time push updates
- **🔍 mDNS Auto-Discovery** - Automatic device detection
- **🔄 OTA Update Support** - Firmware update management
- **🌍 Multi-language Interface** - Complete FR/EN translations
- **⚙️ UI Configuration** - No need to edit configuration.yaml
- **📊 Lovelace Compatible** - Native thermostat cards

## 📦 Quick Installation

1. Install via HACS (add custom repository)
2. Restart Home Assistant
3. Device auto-discovered or add manually
4. Configure and enjoy! 🎉

## 🔧 Requirements

- Home Assistant 2024.1.0+
- ACIT device with firmware v2.0+ (ThermACEC, AccuBloc, etc.)
- Local network connectivity

## 📚 Documentation

- [Complete README](https://github.com/jdu-acit/ACIT_HA_Integration#readme)
- [GitHub Issues](https://github.com/jdu-acit/ACIT_HA_Integration/issues)

## 🎨 Lovelace Card Example

```yaml
type: thermostat
entity: climate.acit_thermacec_temperature_control
```

## 🤖 Automation Example

```yaml
automation:
  - alias: "Thermostat - Night Mode"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.acit_thermacec_temperature_control
        data:
          temperature: 18
```

## 🆘 Support

- [GitHub Issues](https://github.com/jdu-acit/ACIT_HA_Integration/issues)
- [Discussions](https://github.com/jdu-acit/ACIT_HA_Integration/discussions)

## 📝 License

MIT License - See [LICENSE](https://github.com/jdu-acit/ACIT_HA_Integration/blob/main/LICENSE)

