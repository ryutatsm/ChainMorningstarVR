#pragma once

#include <array>
#include <cstdint>
#include <RE/Skyrim.h>
#include "../GameBridgeContract.hpp"
#include "../SceneTransformCore.hpp"
#include "../NativeMeleeDataProbeCore.hpp"

namespace cms::skyrimvr {

// Diagnostic-only, read-only validation of PLANCK's published PlayerCharacter+0x710/0x7E0
// VRMeleeData layout. It reads fields inside PlayerCharacter but never writes or dereferences
// the world/collision pointers contained there.
void ProbeBothHandsNativeMeleeLayoutReadOnly();

class SkyrimVRSceneBridge final : public IGameBridge {
public:
    bool tryGetChainAnchorWorldSU(Vec3& outPositionSU, Vec3& outInitialDirectionWorld) override;
    bool reacquireWeaponNodes() override;
    void releaseWeaponNodes() override;
    void applyVisualFrame(const VisualFrame& frame) override;
    bool updateNativeMeleeHeadProxy(const HeadSweep& sweep) override;
    void submitNativePose(const HeadPose& pose, const HeadSweep& sweep, float frameDt) override;
    std::vector<HeadWorldContact> consumeWorldContacts() override;
    float consumeWorldContactImpulse() override;
    void playChainRattle(float intensity) override;
    void playChainClank(float intensity) override;

    [[nodiscard]] bool visualNodesReady() const noexcept { return anchor_ && head_; }

private:
    RE::NiAVObject* findUnder(RE::NiAVObject* root, std::string_view name) const;
    static Vec3 toCms(const RE::NiPoint3& p);
    static RE::NiPoint3 toNi(Vec3 p);
    static Mat3 toCms(const RE::NiMatrix3& m);
    static RE::NiMatrix3 toNi(const Mat3& m);
    RigidTransform anchorWorldTransformSU() const;
    void writeNodeWorldPose(RE::NiAVObject* node, Vec3 centerWorldM, Vec3 localZWorld, float rollRadians);
    void runReadOnlyNativeMeleeProbe();
    bool currentHandStillOwnsAnchor() const;
    void playChainSound(float intensity);

    RE::NiPointer<RE::NiAVObject> meleeRoot_{};
    RE::NiPointer<RE::NiAVObject> anchor_{};
    std::array<RE::NiPointer<RE::NiAVObject>,14> links_{};
    RE::NiPointer<RE::NiAVObject> head_{};
    bool isLeftHand_{};
    std::uint64_t nativeGeneration_{};
    bool warnedChainSound_{};
    bool readOnlyNativeMotionStateKnown_{};
    bool readOnlyNativeProbeRejectedWarned_{};
    bool readOnlyNativeEnableCollision_{};
    std::uint32_t readOnlyNativeSwingDirection_{};
    std::uintptr_t readOnlyNativeCollisionNode_{};
    std::uintptr_t ownerPlayerAddress_{};
    std::uintptr_t ownerCellAddress_{};
    std::array<RE::BSSoundHandle, 4> chainSounds_{};
    std::size_t nextChainSound_{};
};

} // namespace cms::skyrimvr
