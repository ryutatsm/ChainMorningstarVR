#pragma once

// CommonLibSSE-NG's public headers rely on its upstream PCH for STL, SKSE::stl,
// WinAPI wrappers, fmt/spdlog and related declarations.
#include <SKSE/Impl/PCH.h>

// add_commonlibsse_plugin generates __<Target>Plugin.cpp with "..."sv" literals
// at global scope, so the literal namespace must also be visible globally.
using namespace std::literals;
