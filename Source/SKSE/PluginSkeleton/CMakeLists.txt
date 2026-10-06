cmake_minimum_required(VERSION 3.25)

project(ChainMorningstarVR VERSION 1.0.0 LANGUAGES CXX)
set(CMS_BUILD_LABEL "${PROJECT_VERSION}-audit1")

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(CMS_ENABLE_READONLY_VRMELEE_PROBE
    "Read PLANCK-published VRMeleeData candidate layout for diagnostics; NO writes"
    OFF)

find_package(CommonLibSSE CONFIG REQUIRED)

add_commonlibsse_plugin(${PROJECT_NAME}
    AUTHOR "ChainMorningstarVR"
    SOURCES
        PluginSkeleton.cpp
        SkyrimVRSceneBridge.cpp
        SkyrimVRSceneBridge.hpp
        PlayerInteraction.cpp
        OffhandInput.cpp
        OffhandInput.hpp
        ../OffhandGrabCore.hpp
        ../GripCaptureCore.hpp
        ../OffhandSelectionCore.hpp
        ../PlayerBodyCollisionCore.hpp
        RuntimeService.cpp
        RuntimeService.hpp
        PlayerUpdateHook.cpp
        PlayerUpdateHook.hpp
        PlanckBuildProbe.cpp
        PlanckBuildProbe.hpp
        EorlundVendor.cpp
        EorlundVendor.hpp
        EquipmentDrop.cpp
        EquipmentDrop.hpp
        NativePhysicsBackend.cpp
        NativePhysicsBackend.hpp
        NativeWorldSweep.cpp
        NativeWorldSweep.hpp
        NativeChainCollision.cpp
        NativeChainCollision.hpp
        NativeContactRouter.cpp
        NativeContactRouter.hpp
        WeaponMeshContact.cpp
        WeaponMeshContact.hpp
        ../ContactEpisodeCore.hpp
        ../EquippedSceneCore.hpp
        VRFrameContext.hpp
        ../HeadContactPlanes.hpp
        ../WeaponMeshContactCore.hpp
        ../../ThirdParty/HIGGS/HiggsInterface001.hpp
        ../EquipmentDropCore.hpp
        ../WeaponDimensions.hpp
        ../ChainPhysicsCore.hpp
        ../ChainRuntimeCore.hpp
        ../SceneTransformCore.hpp
        ../NativeMeleeDataProbeCore.hpp
        ../NativeProxyOwnershipCore.hpp
        ../GameBridgeContract.hpp
)

target_include_directories(${PROJECT_NAME} PRIVATE ..)

target_precompile_headers(${PROJECT_NAME}
    PRIVATE
        PCH.h
)

target_compile_definitions(${PROJECT_NAME} PRIVATE CMS_VERSION_STRING="${CMS_BUILD_LABEL}")
if(CMS_ENABLE_READONLY_VRMELEE_PROBE)
    target_compile_definitions(${PROJECT_NAME} PRIVATE CMS_ENABLE_READONLY_VRMELEE_PROBE=1)
else()
    target_compile_definitions(${PROJECT_NAME} PRIVATE CMS_ENABLE_READONLY_VRMELEE_PROBE=0)
endif()

if(MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE /utf-8 /W4 /permissive-)
endif()
