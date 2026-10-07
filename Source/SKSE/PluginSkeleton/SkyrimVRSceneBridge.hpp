#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <RE/Skyrim.h>
#include "../GameBridgeContract.hpp"
#include "../SceneTransformCore.hpp"
#include "../NativeMeleeDataProbeCore.hpp"
#include "../OffhandGrabCore.hpp"
#include "../PlayerBodyCollisionCore.hpp"

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
    HeadHoldTarget updatePlayerInteraction(const HeadPose& head, Vec3 anchorM, float dt) override;
    void queryChainContacts(const std::vector<ChainLinkSweep>& sweeps,
                            std::vector<ChainLinkContact>& contacts) override;
    [[nodiscard]] float chainCollisionScale() const override { return acquiredScale_; }
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
    void writeNodeWorldPose(RE::NiAVObject* node, Vec3 centerWorldM, const Mat3& worldRotation);
    void runReadOnlyNativeMeleeProbe();
    bool currentHandStillOwnsAnchor() const;
    void playChainSound(float intensity, bool heavyImpact);
    void resetPlayerInteraction();

    RE::NiPointer<RE::NiAVObject> sceneRoot_{};
    RE::NiPointer<RE::NiAVObject> weaponSlot_{};
    RE::NiPointer<RE::NiAVObject> weaponRoot_{};
    RE::NiPointer<RE::NiAVObject> anchor_{};
    std::array<RE::NiPointer<RE::NiAVObject>,kChainLinkCount> links_{};
    RE::NiPointer<RE::NiAVObject> head_{};
    bool isLeftHand_{};
    bool inventoryLeft_{};
    bool firstPerson_{};
    bool acquiredLeftMode_{};
    std::uint32_t lastAcquireFailure_{};
    float diagnosticsTime_{};
    unsigned diagnosticSamples_{};
    Vec3 diagnosticAnchor_{};
    float diagnosticMaxTravelM_{};
    std::uint64_t nativeGeneration_{};
    bool nativePrepared_{};
    std::uint8_t nativePrepareRetries_{};
    float nativePrepareCooldownS_{};
    float acquiredScale_{1.0f};
    bool warnedChainSound_{};
    bool warnedImpactSound_{};
    bool readOnlyNativeMotionStateKnown_{};
    bool readOnlyNativeProbeRejectedWarned_{};
    bool readOnlyNativeEnableCollision_{};
    std::uint32_t readOnlyNativeSwingDirection_{};
    std::uintptr_t readOnlyNativeCollisionNode_{};
    std::uintptr_t ownerPlayerAddress_{};
    std::uintptr_t ownerCellAddress_{};
    std::array<RE::BSSoundHandle, 4> chainSounds_{};
    // Four overlapping impacts, each with a body and a metal-strike layer.
    std::array<RE::BSSoundHandle, 8> impactSounds_{};
    std::size_t nextChainSound_{};
    std::size_t nextImpactSound_{};
    unsigned impactSoundSamples_{};
    OffhandGrabState offhandGrab_{};
    std::vector<BodyCapsule> playerCapsules_{};
    float playerBodyDt_{1.0f/90.0f};
    bool reportedPlayerBody_{};
    unsigned grabSamples_{}, bodyContactSamples_{};
    unsigned gripAttemptSamples_{};
    bool gripWasDown_{};
    std::chrono::steady_clock::time_point gripStarted_{};
    unsigned gripProgressSamples_{};
    float gripMaxTargetErrorM_{}, gripMaxChainExcessM_{};
    float lastVisualHeadErrorM_{-1};
    std::uint64_t playerBodyContacts_{};
};

} // namespace cms::skyrimvr
