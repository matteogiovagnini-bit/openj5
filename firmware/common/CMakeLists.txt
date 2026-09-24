# OpenJ5 shared firmware component (ADR-014: C++20, one component per node +
# this common library).
#
# NOTE (2026-09-23): this CMakeLists previously listed 19 source files that do
# not exist (servo/pca9685/l298n/ota/... aspirational skeleton), which made
# every node depending on `common` non-buildable (T-007/T-014 root cause). It
# now lists ONLY files that exist. Nodes 2..6 add their sources back here (or
# in their own component) when they are implemented.

idf_component_register(
    SRCS
        "imu/madgwick.cpp"
        "statemachine/state_machine.cpp"
        "drivers/a4988_driver.cpp"
        "drivers/mpu6050_driver.cpp"
        "comms/wifi_station.cpp"
        "comms/mqtt_client.cpp"
    INCLUDE_DIRS
        "include"
    REQUIRES
        esp_timer
        freertos
        driver
        mqtt
        esp_netif
        esp_event
        esp_wifi
        cxx
)

target_compile_options(${COMPONENT_LIB} PRIVATE
    -std=c++20
    -Wall
    -Wextra
    -Wpedantic
    -Werror
    -Wno-unused-parameter
    -Wno-missing-field-initializers
)

# mTLS certificate access for comms/mqtt_client.cpp (ADR-013). Certs are
# embedded by the NODE's main component; this only gates the code path.
if(CONFIG_OPENJ5_MQTT_TLS)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE OPENJ5_MQTT_TLS=1)
endif()
