idf_component_register(
    SRCS
        "app_main.cpp"
        "balance_controller.cpp"
        "command_handler.cpp"
    INCLUDE_DIRS
        "."
    REQUIRES
        common
        mqtt
        json
        esp_app_format
        driver
        nvs_flash
        esp_netif
        esp_event
        esp_wifi
        esp_timer
        freertos
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

if(CONFIG_OPENJ5_MQTT_TLS)
    # Fail loudly instead of building a firmware that cannot authenticate:
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/certs/ca.crt"
       OR NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/certs/node7.crt"
       OR NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/certs/node7.key")
        message(FATAL_ERROR
            "CONFIG_OPENJ5_MQTT_TLS=y but main/certs/{ca,node7}.crt/.key are "
            "missing. Generate them (firmware/node1_robot_core/docker/certs/"
            "generate.sh) and copy to main/certs/ - or build with TLS off for "
            "bench only.")
    endif()
    target_compile_definitions(${COMPONENT_LIB} PRIVATE OPENJ5_MQTT_TLS=1)
    # Symbols consumed by firmware/common/comms/mqtt_client.cpp:
    #   _binary_certs_ca_crt_start/_end, _binary_certs_node7_crt_start/_end,
    #   _binary_certs_node7_key_start/_end (IDF appends the NUL byte).
    target_add_binary_data(${COMPONENT_LIB} "certs/ca.crt")
    target_add_binary_data(${COMPONENT_LIB} "certs/node7.crt")
    target_add_binary_data(${COMPONENT_LIB} "certs/node7.key")
endif()
