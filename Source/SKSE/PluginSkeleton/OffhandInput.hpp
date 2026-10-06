#pragma once
#include <SKSE/SKSE.h>
#include "../OffhandInputCore.hpp"

namespace cms::skyrimvr {
void RegisterOffhandInput(const SKSE::LoadInterface* skse);
GripInput ReadLeftGrab();
void ArmLeftGrab(bool arm);
void ResetOffhandInput();
} // namespace cms::skyrimvr
