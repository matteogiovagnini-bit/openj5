# ADR-015: MQTT as Primary Transport Protocol

## Status
Accepted

## Context
Six nodes must exchange logical commands and events over mixed links (RPi Ethernet, ESP32 WiFi 2.4GHz). Requirements: low overhead on microcontrollers, QoS options, retained messages for state, broker-based decoupling, TLS support, and mature ESP32 client libraries. Alternative transports (ROS 2 DDS, Zenoh, gRPC, WebSocket) serve different niches and must remain swappable per ADR-003.

## Decision
**MQTT 3.1.1/5.0 (Mosquitto broker) is the primary transport** for all node communication:

- Broker: Mosquitto 2.0 containerized on Node 1 (mTLS listener :8883, WebSocket :9001, ACL per node).
- Topic schema versioned: `openj5/v<major>/<node>/<cmd|evt|telemetry|ota|status>` (see NAMING_CONVENTIONS §4).
- Payloads: compact JSON; commands carry **logical operations** (`look_at`, `wave`), never servo angles.
- QoS: 0 for high-rate telemetry, 1 for commands/events, retained messages for last-known state.
- Healthcheck via `$SYS/broker/version`; persistent sessions for reconnecting nodes.

All access through `ICommunicationGateway` (ADR-003); MQTT appears in exactly one adapter (`MqttGateway`, aiomqtt on Python side / esp-mqtt on firmware side).

## Alternatives Considered
1. **ROS 2 DDS as primary** - Rejected: heavy for ESP32 (rclwifi footprint), discovery traffic on constrained WiFi, ties platform to ROS ecosystem (NON_GOALS §2); ROS 2 remains an optional bridge.
2. **HTTP/REST polling from ESP32** - Rejected: no push semantics, connection overhead, poor latency for realtime events.
3. **Zenoh** - Deferred: promising for edge latency, but ESP32 client maturity and team familiarity favor MQTT for v1; gateway pattern allows adding it later without code changes.
4. **Custom UDP protocol** - Rejected: reimplementing reliability/security that MQTT+TLS already provide.

## Consequences
**Positive:**
- Proven on ESP32 (esp-mqtt), trivially testable with standard tooling (mosquitto_pub/sub).
- Broker gives persistence of sessions, retained state and ACL-based security zoning.
- Latency adequate for logical-command control model (trajectories executed locally on ESP32).

**Negative:**
- Single broker = central failure point → mitigated by broker healthcheck + node-side autonomous fail-safe (ADR-009) and possible broker HA later.
- JSON parsing cost on MCU - acceptable at command rates; binary payloads deferred until profiling demands it.

## Implementation Notes
- Broker config: `docker/config/mosquitto/mosquitto.conf` + `acl`; stabilized during session 2026-08-13 (healthcheck on `$SYS/broker/version`, anonymous read limited to `$SYS/#`, max_packet_size option naming, VOLUME for log dir).
- ROS 2 coexistence via rosbridge container (optional service in docker-compose).

## Related ADRs
- ADR-003: Communication Gateway Pattern (MQTT is one adapter)
- ADR-004: Event-Driven Architecture (bus events bridged to/from MQTT)
- ADR-013: Security (mTLS on the MQTT listener)
