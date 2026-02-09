# Home Assistant MQTT Integration

The Schellenberg USB Hack addon now supports MQTT autodiscovery for seamless integration with Home Assistant.

## Features

- **Automatic Device Discovery**: All paired Schellenberg devices are automatically discovered by Home Assistant as cover entities
- **Real-time State Updates**: Device states are published to MQTT whenever commands are received
- **Bidirectional Control**: Control devices through Home Assistant UI, automations, or direct MQTT commands
- **Connection Monitoring**: Availability tracking to show when the addon is online/offline

## Configuration

Add the following MQTT settings to your addon configuration:

```yaml
mqtt_host: core-mosquitto      # Mosquitto broker hostname (default for HA)
mqtt_port: 1883                # MQTT broker port
mqtt_user: null                # Optional: MQTT username
mqtt_password: null            # Optional: MQTT password
```

For standard Home Assistant installations with the Mosquitto addon, the default settings should work without authentication.

## MQTT Topics

### Discovery Topics
Each device publishes its configuration to:
```
homeassistant/cover/schellenberg_{sender_id}_{enumerator}/config
```

### Command Topics
Send commands to devices:
```
schellenberg/{sender_id}_{enumerator}/set
```

Supported payloads:
- `OPEN` - Open the cover (move up)
- `CLOSE` - Close the cover (move down)
- `STOP` - Stop movement

### State Topics
Device states are published to:
```
schellenberg/{sender_id}_{enumerator}/state
```

Possible states:
- `opening` - Cover is moving up
- `closing` - Cover is moving down
- `stopped` - Cover has stopped
- `open` - Cover is fully open (if position tracking available)
- `closed` - Cover is fully closed (if position tracking available)

### Availability Topic
Addon availability status:
```
schellenberg/availability
```

Payloads: `online` or `offline`

## Home Assistant Integration

Once configured, your Schellenberg devices will automatically appear in Home Assistant as cover entities. You can:

1. **Control via UI**: Use the Home Assistant dashboard to open, close, or stop covers
2. **Create Automations**: Trigger actions based on cover state or control covers in automations
3. **Use in Scripts**: Include cover controls in your scripts
4. **Voice Control**: Control via voice assistants connected to Home Assistant

### Example Automation

```yaml
automation:
  - alias: "Close covers at sunset"
    trigger:
      - platform: sun
        event: sunset
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.schellenberg_*
```

## API Endpoints

### Republish Autodiscovery
Manually trigger republishing of all device configurations:
```
POST /api/homeassistant/republish
```

This is useful if:
- You've restarted Home Assistant
- MQTT broker was restarted
- Devices aren't showing up correctly

## Troubleshooting

### Devices not appearing in Home Assistant

1. Check MQTT broker is running: `sudo docker ps | grep mosquitto`
2. Verify addon is connected to MQTT: Check addon logs for "Home Assistant MQTT worker started"
3. Manually republish configs: `POST /api/homeassistant/republish`
4. Check MQTT discovery is enabled in Home Assistant configuration

### Commands not working

1. Verify devices are paired: Check `/api/devices/paired`
2. Check MQTT logs for command reception
3. Verify device enumerators match your physical devices
4. Check addon logs for error messages

### State not updating

1. Ensure devices are sending feedback messages
2. Check that the serial connection is stable
3. Verify MQTT broker is receiving state updates

## Manual MQTT Testing

You can test the MQTT interface using mosquitto_pub/sub:

```bash
# Subscribe to all Schellenberg topics
mosquitto_sub -h core-mosquitto -t 'schellenberg/#' -v

# Send a command to open a cover
mosquitto_pub -h core-mosquitto -t 'schellenberg/XXXXXX_XX/set' -m 'OPEN'

# Check availability
mosquitto_sub -h core-mosquitto -t 'schellenberg/availability' -v
```

Replace `XXXXXX_XX` with your actual sender_id and enumerator.
