#pragma once

#include <SKSE/Impl/PCH.h>

// CommonLibSSE-NG's add_commonlibsse_plugin() generates a metadata TU that uses
// "..."sv" at global scope. Make the standard literal namespace visible to it.
using namespace std::literals;
