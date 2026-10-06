#pragma once
#include <SKSE/SKSE.h>
#include "../GripCaptureCore.hpp"

namespace cms::skyrimvr {
void RegisterOffhandInput(const SKSE::LoadInterface* skse);
GripInput ReadLeftGrip();
void ArmLeftGrip(bool arm);
void ResetOffhandInput();
} // namespace cms::skyrimvr
