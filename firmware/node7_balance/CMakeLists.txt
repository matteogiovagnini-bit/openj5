cmake_minimum_required(VERSION 3.16)

# Node 7 Balance Controller - ESP-IDF project (ADR-017).
# Shared component: firmware/common (HAL stepper, MPU6050+Madgwick, WiFi/MQTT).

set(PROJECT_VER "1.0.0")  # matches config/node7_balance/node.json -> node.version

list(APPEND EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../common")

# sdkconfig.defaults for everyone + optional uncommitted local overrides
# (WiFi credentials, MQTT host/TLS: see README.md).
set(SDKCONFIG_DEFAULTS "sdkconfig.defaults")
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.local")
    list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.local")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(openj5_node7_balance)

# ADR-014 compiles our code with -Wall -Wextra -Wpedantic -Werror, but ESP-IDF
# headers are not pedantic-clean (GCC #include_next in newlib's
# platform_include/stdio.h, zero-length arrays in esp_wifi_types*.h, ...) and
# IDF passes them as plain -I: any IDF header pulled in by our sources would
# fail -Werror. GCC ignores a plain -I when the same directory is also given
# with -isystem, so demote every IDF component include directory to SYSTEM for
# our two components. Our own dirs (main/, common/include) are skipped on
# purpose and stay fully checked. This applies to both build paths - idf.py
# (CI, IDF 5.2.2) and PlatformIO (local, IDF 5.5) - because both consume this
# file.
function(openj5_collect_idf_targets dir out_var)
    set(collected "")
    get_property(dirs_here DIRECTORY "${dir}" PROPERTY SUBDIRECTORIES)
    get_property(tgts_here DIRECTORY "${dir}" PROPERTY BUILDSYSTEM_TARGETS)
    foreach(tgt IN LISTS tgts_here)
        if(tgt MATCHES "^__idf_")
            list(APPEND collected "${tgt}")
        endif()
    endforeach()
    foreach(sub IN LISTS dirs_here)
        if(IS_DIRECTORY "${sub}")
            openj5_collect_idf_targets("${sub}" sub_collected)
            list(APPEND collected ${sub_collected})
        endif()
    endforeach()
    set(${out_var} "${collected}" PARENT_SCOPE)
endfunction()

openj5_collect_idf_targets("${CMAKE_CURRENT_SOURCE_DIR}" openj5_idf_targets)
set(openj5_system_includes "")
foreach(tgt IN LISTS openj5_idf_targets)
    if(NOT tgt MATCHES "^__idf_(main|common)$")  # ours must stay non-system
        get_target_property(tgt_incs ${tgt} INTERFACE_INCLUDE_DIRECTORIES)
        if(tgt_incs)
            list(APPEND openj5_system_includes ${tgt_incs})
        endif()
    endif()
endforeach()
if(openj5_system_includes)
    list(REMOVE_DUPLICATES openj5_system_includes)
    foreach(ours IN ITEMS __idf_main __idf_common)
        if(TARGET ${ours})
            target_include_directories(${ours} SYSTEM PRIVATE
                                        ${openj5_system_includes})
        endif()
    endforeach()
endif()
list(LENGTH openj5_idf_targets openj5_targets_n)
list(LENGTH openj5_system_includes openj5_incs_n)
message(STATUS "OpenJ5: ${openj5_targets_n} IDF targets -> ${openj5_incs_n} "
               "include dirs as -isystem (ADR-014)")
