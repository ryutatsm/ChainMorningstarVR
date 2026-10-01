cmake_minimum_required(VERSION 3.25)

project(ChainMorningstarVR VERSION 0.4.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(CommonLibSSE CONFIG REQUIRED)

add_commonlibsse_plugin(${PROJECT_NAME}
    AUTHOR "ChainMorningstarVR"
    SOURCES
        PluginSkeleton.cpp
)

target_precompile_headers(${PROJECT_NAME}
    PRIVATE
        PCH.h
)

if(MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE /utf-8 /W4 /permissive-)
endif()
