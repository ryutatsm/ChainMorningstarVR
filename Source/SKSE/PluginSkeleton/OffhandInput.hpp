#pragma once
#include <SKSE/SKSE.h>

namespace cms::skyrimvr {
struct GripInput { bool fresh{}, down{}, captured{}; };
void RegisterOffhandInput(const SKSE::LoadInterface* skse);
GripInput ReadLeftGrip();
void ArmLeftGrip(bool arm);
void ResetOffhandInput();
} // namespace cms::skyrimvr
