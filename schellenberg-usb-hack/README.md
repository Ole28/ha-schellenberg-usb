# Home Assistant Add-on: Schellenberg USB Hack

_Control Schellenberg devices via the Schellenberg USB QIVICON adapter._

![Supports amd64 Architecture][amd64-shield]

[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg

## About

This add-on allows you to control Schellenberg devices (blinds, shutters, etc.) using the Schellenberg USB QIVICON adapter. It provides:

- **Web UI**: Modern interface for pairing and controlling devices
- **REST API**: Full API for device management
- **MQTT Autodiscovery**: Automatic integration with Home Assistant via MQTT
- **Real-time Updates**: Server-Sent Events for live device status

## Features

### MQTT Integration (NEW!)

All paired devices are automatically discovered by Home Assistant as cover entities through MQTT:

- Automatic device discovery in Home Assistant
- Control devices through Home Assistant UI
- Real-time state updates
- Use in automations and scripts
- Voice control support

See [MQTT.md](MQTT.md) for detailed MQTT documentation.

### Web Interface

Access the web UI through the Ingress panel to:
- View all discovered devices
- Pair new devices
- Rename devices
- Control devices manually
- Monitor device activity

### API Endpoints

- `GET /api/devices/all` - List all discovered senders
- `GET /api/devices/paired` - Get paired devices
- `GET /api/devices/specific/{sender_id}/{enumerator}` - Get specific device
- `POST /api/devices/specific/{sender_id}/rename` - Rename a sender
- `POST /api/devices/specific/{sender_id}/{enumerator}/rename` - Rename a device
- `POST /api/devices/specific/{sender_id}/{enumerator}/remove` - Remove a device
- `POST /api/devices/specific/{sender_id}/{enumerator}/command` - Send command to device
- `POST /api/devices/specific/{receiver_id}/{enumerator}/pair` - Pair a new device
- `GET /api/devices/events` - Server-Sent Events stream
- `POST /api/homeassistant/republish` - Republish MQTT autodiscovery configs

## Configuration

```yaml
serial: /dev/ttyUSB0          # USB device path (select from dropdown)
mqtt_host: core-mosquitto      # MQTT broker hostname
mqtt_port: 1883                # MQTT broker port
mqtt_user: null                # Optional: MQTT username
mqtt_password: null            # Optional: MQTT password
```

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Schellenberg USB Hack" add-on
3. Configure the serial port (select your USB device from the dropdown)
4. Configure MQTT settings (defaults should work for standard HA installations)
5. Start the add-on
6. Check the logs to ensure everything is working
7. Access the web UI through the Ingress panel

## Usage

### Pairing Devices

1. Open the web UI
2. Press the pairing button on your physical Schellenberg device
3. Click "Pair" in the web UI when prompted
4. The device will be added and automatically discovered in Home Assistant

### Controlling Devices

**Via Home Assistant UI:**
- Navigate to your cover entities
- Use the open/close/stop controls

**Via Automations:**
```yaml
service: cover.close_cover
target:
  entity_id: cover.schellenberg_xxxxxx_xx
```

**Via API:**
```bash
curl -X POST "http://homeassistant.local:8123/api/devices/specific/XXXXXX/XX/command?command=UP"
```

**Via MQTT:**
```bash
mosquitto_pub -h core-mosquitto -t 'schellenberg/XXXXXX_XX/set' -m 'OPEN'
```

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/home-assistant/addons-example).

## Documentation

- [MQTT Integration Guide](MQTT.md) - Detailed MQTT documentation
- [Home Assistant Cover Integration](https://www.home-assistant.io/integrations/cover/) - Home Assistant cover platform docs
