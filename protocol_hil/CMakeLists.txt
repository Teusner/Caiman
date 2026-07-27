cmake_minimum_required(VERSION 3.16)
project(caiman_protocol_hil C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_library(caiman_protocol
    shared/src/caiman_protocol.c
)
target_include_directories(caiman_protocol PUBLIC shared/include)
target_compile_options(caiman_protocol PRIVATE -Wall -Wextra -Wpedantic -Werror)
target_link_libraries(caiman_protocol PUBLIC mbedcrypto m)

add_library(nrf24_sim
    shared/src/nrf24_sim.c
)
target_include_directories(nrf24_sim PUBLIC shared/include)
target_compile_options(nrf24_sim PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(caiman_protocol_test tests/test_protocol.c)
target_link_libraries(caiman_protocol_test PRIVATE caiman_protocol)
target_compile_options(caiman_protocol_test PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(nrf24_sim_test tests/test_nrf24_sim.c)
target_link_libraries(nrf24_sim_test PRIVATE nrf24_sim)
target_compile_options(nrf24_sim_test PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(caiman_pi raspberry/main.c)
target_link_libraries(caiman_pi PRIVATE caiman_protocol nrf24_sim)
target_compile_options(caiman_pi PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(caiman_esp_log raspberry/esp_log.c)
target_compile_options(caiman_esp_log PRIVATE -Wall -Wextra -Wpedantic -Werror)

enable_testing()
add_test(NAME caiman_protocol_test COMMAND caiman_protocol_test)
add_test(NAME nrf24_sim_test COMMAND nrf24_sim_test)
