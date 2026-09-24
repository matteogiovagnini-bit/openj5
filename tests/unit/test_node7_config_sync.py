"""T-026: config parity across firmware Kconfig, node.json, bench and docs.

The Node 7 firmware reads every constant from `main/Kconfig.projbuild` while
the host side reads `config/node7_balance/node.json`: two sources of truth
drift silently (zero-magic-numbers rule, KNOWLEDGE_BASE). This test pins them
together, together with the step math of ADR-017 and the wiring guide.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_JSON = ROOT / "config" / "node7_balance" / "node.json"
BENCH_JSON = ROOT / "config" / "bench" / "balance.json"
TOPICS_JSON = ROOT / "config" / "common" / "topics.json"
KCONFIG = ROOT / "firmware" / "node7_balance" / "main" / "Kconfig.projbuild"
PIO_INI = ROOT / "firmware" / "node7_balance" / "platformio.ini"
GEN_CERTS = ROOT / "firmware" / "node1_robot_core" / "docker" / "certs"
WIRING_DOC = ROOT / "docs" / "hardware" / "BENCH_BALANCE.md"


def _kconfig() -> tuple[dict[str, int], dict[str, str], dict[str, str]]:
    """Parse default values of int/string/bool options from Kconfig.projbuild."""
    text = KCONFIG.read_text(encoding="utf-8")
    ints = {
        name: int(value)
        for name, value in re.findall(
            r"config (OPENJ5_\w+)\s*\n\s+int[^\n]*\n\s+default (-?\d+)", text
        )
    }
    strings = {
        name: value
        for name, value in re.findall(
            r'config (OPENJ5_\w+)\s*\n\s+string[^\n]*\n\s+default "([^"]*)"', text
        )
    }
    bools = {
        name: value
        for name, value in re.findall(
            r"config (OPENJ5_\w+)\s*\n\s+bool[^\n]*\n\s+default (y|n)", text
        )
    }
    return ints, strings, bools


def _node() -> dict:
    return json.loads(NODE_JSON.read_text(encoding="utf-8"))


def test_step_math_and_travel_limits():
    """12800 jsteps/rev -> 35.556 jsteps/deg -> +/-35 deg = +/-1244 jsteps."""
    node = _node()
    stepper = node["steppers"][0]
    jsteps_per_rev = (
        stepper["steps_per_rev"] * stepper["microsteps"] * stepper["gear_ratio"]
    )
    assert jsteps_per_rev == 12800
    jsteps_per_deg = jsteps_per_rev / 360.0
    expected = round(node["balance"]["max_tilt_deg"] * jsteps_per_deg)
    assert expected == 1244  # the old 4445 (= 125 deg!) must not come back
    assert stepper["limits"]["min_steps"] == -expected
    assert stepper["limits"]["max_steps"] == expected
    assert node["balance"]["max_tilt_deg"] == 35.0


def test_kconfig_matches_node_json_stepper():
    ints, _, _ = _kconfig()
    node = _node()
    joint = node["stepper_driver"]["config"]["a4988"]["balance_joint"]
    stepper = node["steppers"][0]
    assert ints["OPENJ5_PIN_STEP"] == joint["step_pin"] == 4
    assert ints["OPENJ5_PIN_DIR"] == joint["dir_pin"] == 5
    assert ints["OPENJ5_PIN_ENABLE"] == joint["enable_pin"] == 6
    assert ints["OPENJ5_STEPS_PER_REV"] == stepper["steps_per_rev"] == 200
    assert ints["OPENJ5_MICROSTEPS"] == joint["microsteps"] == 16
    assert ints["OPENJ5_GEAR_RATIO"] == stepper["gear_ratio"] == 4
    assert ints["OPENJ5_MAX_VELOCITY"] == stepper["max_speed_steps_s"] == 1600
    assert ints["OPENJ5_MAX_ACCEL"] == stepper["max_accel_steps_s2"] == 800
    assert stepper["limits"]["max_acceleration_steps_s2"] == 800  # same value
    assert ints["OPENJ5_POS_LIMIT_STEPS"] == stepper["limits"]["max_steps"] == 1244


def test_kconfig_matches_node_json_balance_and_safety():
    ints, strings, bools = _kconfig()
    node = _node()
    balance = node["balance"]
    safety = node["safety"]
    assert ints["OPENJ5_TARGET_PITCH_DEG"] == balance["target_pitch_deg"] == 0
    assert ints["OPENJ5_MAX_TILT_DEG"] == balance["max_tilt_deg"] == 35
    assert ints["OPENJ5_CONTROL_HZ"] == balance["control_hz"] == 100
    assert float(strings["OPENJ5_DEADBAND_DEG"]) == balance["deadband_deg"] == 0.5
    pid = balance["pid"]
    assert float(strings["OPENJ5_PID_KP"]) == pid["kp"] == 15.0
    assert float(strings["OPENJ5_PID_KI"]) == pid["ki"] == 1.0
    assert float(strings["OPENJ5_PID_KD"]) == pid["kd"] == 0.3
    # Kconfig stores symmetric magnitudes (no negative int defaults).
    assert ints["OPENJ5_PID_OUTPUT_MAX"] == pid["output_max"] == 1600
    assert -ints["OPENJ5_PID_OUTPUT_MAX"] == pid["output_min"] == -1600
    assert ints["OPENJ5_PID_INTEGRAL_LIMIT"] == pid["integral_max"] == 4000
    assert -ints["OPENJ5_PID_INTEGRAL_LIMIT"] == pid["integral_min"] == -4000
    assert ints["OPENJ5_DEADMAN_TIMEOUT_MS"] == safety["deadman_timeout_ms"] == 250
    assert ints["OPENJ5_WATCHDOG_TIMEOUT_MS"] == safety["watchdog_timeout_ms"] == 1000
    # Coils OFF at boot (node.json balance/safety both say so).
    assert bools["OPENJ5_ENABLED_ON_BOOT"] == "n"
    assert not balance["enabled_on_boot"]
    assert not safety["enable_on_boot"]


def test_kconfig_matches_node_json_imu_and_topics():
    ints, strings, _ = _kconfig()
    node = _node()
    imu = node["imu"]
    assert ints["OPENJ5_IMU_ADDR"] == imu["address"] == 104
    assert ints["OPENJ5_IMU_SAMPLE_HZ"] == imu["sample_rate_hz"] == 200
    assert imu["type"] == "mpu6050"
    assert imu["fusion"] == "madgwick"  # implemented in firmware/common/imu

    assert strings["OPENJ5_TOPIC_PREFIX"] == node["network"]["mqtt"]["topic_prefix"]
    assert strings["OPENJ5_MQTT_CLIENT_ID"] == node["network"]["mqtt"]["client_id"]
    topics = json.loads(TOPICS_JSON.read_text(encoding="utf-8"))
    prefix = strings["OPENJ5_TOPIC_PREFIX"]
    assert topics["nodes"]["node7"]["cmd"] == f"{prefix}/cmd"
    assert topics["nodes"]["node7"]["state"] == f"{prefix}/state"


def test_bench_config_matches_node_json_limits():
    bench = json.loads(BENCH_JSON.read_text(encoding="utf-8"))
    stepper = _node()["steppers"][0]
    assert bench["stepper"]["microsteps"] == stepper["microsteps"]
    assert bench["stepper"]["steps_per_rev"] == stepper["steps_per_rev"]
    assert bench["stepper"]["gear_ratio"] == stepper["gear_ratio"]
    assert bench["limits"] == stepper["limits"]


def test_wiring_doc_lists_the_firmware_pins():
    doc = WIRING_DOC.read_text(encoding="utf-8")
    ints, _, _ = _kconfig()
    for key in ("OPENJ5_PIN_STEP", "OPENJ5_PIN_DIR", "OPENJ5_PIN_ENABLE"):
        assert f"GPIO{ints[key]}" in doc, f"{key}=GPIO{ints[key]} missing in wiring doc"
    assert "GPIO8" in doc and "GPIO9" in doc  # I2C defaults
    assert "1244" in doc  # travel limit consistent with configs


def test_certs_script_generates_node7():
    generate = (GEN_CERTS / "generate.sh").read_text(encoding="utf-8")
    assert re.search(r"for i in 1 2 3 4 5 6 7;", generate), "node7 cert missing"
    assert "node7" in generate


def test_platformio_ini_matches_project():
    """VSCode/PlatformIO must build the same chip/project as idf.py and CI.

    platformio.ini carries the ESP-IDF version constraint (platform 6.12.x =
    IDF v5.5 vs CI container v5.2.2): pinning, board and src_dir are part of
    the contract and must not drift from the idf.py project.
    """
    text = "\n".join(
        line.split(";", 1)[0] for line in PIO_INI.read_text(encoding="utf-8").splitlines()
    )  # drop inline ini comments before anchoring on `$`
    assert "platform = platformio/espressif32 @" in text  # pinned, no `latest`
    assert "board = esp32-s3-devkitc-1" in text  # == idf.py set-target esp32s3
    assert "framework = espidf" in text
    assert re.search(r"^\s*src_dir\s*=\s*main\s*$", text, re.MULTILINE)  # IDF layout
    assert re.search(r"^\s*monitor_speed\s*=\s*115200\s*$", text, re.MULTILINE)
    assert PIO_INI.parent.joinpath("CMakeLists.txt").exists()  # shared project
    # The IDF MQTT component is named `mqtt` (components/mqtt, esp-mqtt
    # submodule): `esp_mqtt` never existed and fails every build (first
    # `pio run` red). Check every CMakeLists in Node 7's build graph.
    for cmake in (
        ROOT / "firmware" / "common" / "CMakeLists.txt",
        ROOT / "firmware" / "node7_balance" / "main" / "CMakeLists.txt",
        ROOT / "firmware" / "node2_head" / "CMakeLists.txt",
    ):
        assert "esp_mqtt" not in cmake.read_text(encoding="utf-8"), cmake
    # `.pio/` build dir and the per-env sdkconfig (PlatformIO bakes
    # sdkconfig.local overrides - WiFi credentials - into sdkconfig.node7)
    # must never be committed.
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "firmware/**/.pio/" in gitignore
    node_gitignore = (PIO_INI.parent / ".gitignore").read_text(encoding="utf-8")
    assert "sdkconfig.*" in node_gitignore
    assert "!sdkconfig.defaults" in node_gitignore
