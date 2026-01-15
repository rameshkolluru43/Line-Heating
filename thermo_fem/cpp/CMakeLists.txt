cmake_minimum_required(VERSION 3.16)
project(thermo_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
  message(WARNING "pybind11 not found; Python bindings will not build. Install pybind11 or set PYBIND11_ROOT.")
endif()

add_library(thermo_core STATIC
  src/heat.cpp
  src/mechanics.cpp
)

target_include_directories(thermo_core PUBLIC include)

if(pybind11_FOUND)
  pybind11_add_module(thermo_bindings src/bindings.cpp)
  target_link_libraries(thermo_bindings PRIVATE thermo_core)
endif()
