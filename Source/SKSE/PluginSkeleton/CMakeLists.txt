cmake_minimum_required(VERSION 3.25)

project(ChainMorningstarVR VERSION 0.4.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(CommonLibSSE CONFIG REQUIRED)

add_commonlibsse_plugin(${PROJECT_NAME}
    SOURCES
        PluginSkeleton.cpp
)

target_precompile_headers(${PROJECT_NAME} PRIVATE PCH.h)
target_compile_features(${PROJECT_NAME} PRIVATE cxx_std_23)

if(MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE /W4 /permissive- /utf-8)
endif()
