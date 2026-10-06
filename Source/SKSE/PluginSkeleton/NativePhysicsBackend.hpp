#pragma once

#include <RE/Skyrim.h>
#include <vector>
#include "../ChainRuntimeCore.hpp"
#include "../SceneTransformCore.hpp"

namespace cms::skyrimvr {

struct NativeHeadSnapshot {
    Vec3 centerM{};
    Mat3 rotation{};
    Vec3 velocityMps{};
    float shapeScale{1.0f};
    std::uintptr_t bodyIdentity{};
    std::uint64_t generation{};
    std::uint64_t physicsStep{};
    bool leftHand{};
    bool ready{};
};

// All public calls below are game-thread calls. The implementation copies poses
// for the HIGGS prephysics callback, and copies contacts back without retaining
// collision-thread pointers in the gameplay queue.
class NativePhysicsBackend {
public:
    static NativePhysicsBackend& GetSingleton();
    bool Initialize();  // SKSE PostPostLoad, after HIGGS's PostLoad API registration.
    bool BeginSession(RE::NiAVObject* weaponRoot, bool leftHand, std::uint64_t generation);
    void EndSession();
    void SubmitPose(const HeadPose& pose, float frameDeltaS);
    std::vector<HeadWorldContact> ConsumeContacts();
    [[nodiscard]] NativeHeadSnapshot Snapshot() const;
    [[nodiscard]] bool Available() const;
};

}  // namespace cms::skyrimvr
