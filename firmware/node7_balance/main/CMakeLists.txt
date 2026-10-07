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
    #   _binary_certs_node7_key_start/_end. IDF's target_add_binary_data would
    #   defer the .S to a ninja custom command, but PlatformIO's SCons phase
    #   compiles main's codemodel sources BEFORE ninja runs and dies on the
    #   missing file: run IDF's embed script at configure time instead
    #   (TEXT = NUL-terminated, what mbedtls's PEM parser expects) and
    #   re-run configure when a cert changes. CI builds with TLS off.
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/certs/ca.crt"
        "${CMAKE_CURRENT_SOURCE_DIR}/certs/node7.crt"
        "${CMAKE_CURRENT_SOURCE_DIR}/certs/node7.key")
    set(_cert_files ca.crt node7.crt node7.key)
    set(_cert_symbols certs_ca_crt certs_node7_crt certs_node7_key)
    list(LENGTH _cert_files _certs_n)
    math(EXPR _certs_last "${_certs_n} - 1")
    foreach(_i RANGE ${_certs_last})
        list(GET _cert_files ${_i} _cert_file)
        list(GET _cert_symbols ${_i} _cert_symbol)
        set(_cert_asm "${CMAKE_BINARY_DIR}/${_cert_symbol}.S")
        execute_process(
            COMMAND "${CMAKE_COMMAND}"
                -D "DATA_FILE=${CMAKE_CURRENT_SOURCE_DIR}/certs/${_cert_file}"
                -D "SOURCE_FILE=${_cert_asm}"
                -D "VARIABLE_BASENAME=${_cert_symbol}"
                -D "FILE_TYPE=TEXT"
                -P "$ENV{IDF_PATH}/tools/cmake/scripts/data_file_embed_asm.cmake"
            RESULT_VARIABLE _cert_embed_result)
        if(_cert_embed_result)
            message(FATAL_ERROR "Failed to embed certs/${_cert_file} into ${_cert_asm}")
        endif()
        target_sources(${COMPONENT_LIB} PRIVATE "${_cert_asm}")
    endforeach()
endif()
