cmake_minimum_required(VERSION 3.16)

# Set component requirements
set(COMPONENT_REQUIRES
    common
    esp_mqtt
    driver
    i2c
    spi_flash
    nvs_flash
    esp_timer
    freertos
    esp_https_ota
    esp_netif
    esp_event
    esp_wifi
    mbedtls
    cxx
    json
)

# Include directories
target_include_directories(${COMPONENT_LIB} PRIVATE
    include
    ../common/include
)

# Source files
target_sources(${COMPONENT_LIB} PRIVATE
    src/main.cpp
    src/head_controller.cpp
    src/servo_manager.cpp
    src/motion_primitives.cpp
    src/display_manager.cpp
    src/audio_manager.cpp
    src/sensor_manager.cpp
    src/communication.cpp
    src/state_machine.cpp
    src/ota_handler.cpp
)

# Compile options for C++20
target_compile_options(${COMPONENT_LIB} PRIVATE
    -std=c++20
    -Wall
    -Wextra
    -Wpedantic
    -Werror
    -Wno-unused-parameter
    -Wno-missing-field-initializers
)

# Link libraries
target_link_libraries(${COMPONENT_LIB} PRIVATE
    common
    ${IDF_MQTT_LIB}
    ${IDF_JSON_LIB}
)