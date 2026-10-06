#include "SkyrimVRSceneBridge.hpp"
#include "PlanckBuildProbe.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <SKSE/SKSE.h>

#if defined(CMS_ENABLE_NATIVE_MELEE_PROXY) && CMS_ENABLE_NATIVE_MELEE_PROXY
#error "The unverified VRMeleeData collisionNode write path was removed; implement a verified Havok backend."
#endif

namespace cms::skyrimvr {

namespace {

bool nativeReadOnlyLayoutSupported()
{
    // The candidate offsets describe Skyrim VR 1.4.15, not arbitrary future VR
    // runtimes. Read bytes into a trivial snapshot; never alias live NiPointers.
    return REL::Module::IsVR() && REL::Module::get().version() == REL::Version{1, 4, 15, 0};
}

NativeVRMeleeDataProbeLayout readNativeMeleeSnapshot(std::uintptr_t address)
{
    NativeVRMeleeDataProbeLayout snapshot{};
    std::memcpy(&snapshot, reinterpret_cast<const void*>(address), sizeof(snapshot));
    return snapshot;
}

const char* identifyKnownVrOffsetNode(const RE::VR_NODE_DATA* vr, std::uintptr_t raw) noexcept
{
    if (!vr || !raw) return "null";

    struct NamedNode {
        const char* name;
        const RE::NiAVObject* node;
    };

    const NamedNode nodes[] = {
        {"LeftWeaponOffsetNode", vr->LeftWeaponOffsetNode.get()},
        {"LeftCrossbowOffsetNode", vr->LeftCrossbowOffsetNode.get()},
        {"LeftMeleeWeaponOffsetNode", vr->LeftMeleeWeaponOffsetNode.get()},
        {"LeftStaffWeaponOffsetNode", vr->LeftStaffWeaponOffsetNode.get()},
        {"LeftShieldOffsetNode", vr->LeftShieldOffsetNode.get()},
        {"RightShieldOffsetNode", vr->RightShieldOffsetNode.get()},
        {"SecondaryMagicOffsetNode", vr->SecondaryMagicOffsetNode.get()},
        {"SecondaryStaffMagicOffsetNode", vr->SecondaryStaffMagicOffsetNode.get()},
        {"RightWeaponOffsetNode", vr->RightWeaponOffsetNode.get()},
        {"RightCrossbowOffsetNode", vr->RightCrossbowOffsetNode.get()},
        {"RightMeleeWeaponOffsetNode", vr->RightMeleeWeaponOffsetNode.get()},
        {"RightStaffWeaponOffsetNode", vr->RightStaffWeaponOffsetNode.get()},
        {"PrimaryMagicOffsetNode", vr->PrimaryMagicOffsetNode.get()},
        {"PrimaryStaffMagicOffsetNode", vr->PrimaryStaffMagicOffsetNode.get()},
        {"NPCLHnd", vr->NPCLHnd.get()},
        {"NPCRHnd", vr->NPCRHnd.get()}
    };

    for (const auto& e : nodes) {
        if (reinterpret_cast<std::uintptr_t>(e.node) == raw) {
            return e.name;
        }
    }
    return "unmatched-known-vr-node";
}



} // namespace

void ProbeBothHandsNativeMeleeLayoutReadOnly()
{
#if defined(CMS_ENABLE_READONLY_VRMELEE_PROBE) && CMS_ENABLE_READONLY_VRMELEE_PROBE
    if (!nativeReadOnlyLayoutSupported()) return;
    auto* player = RE::PlayerCharacter::GetSingleton();
    auto* vr = player ? player->GetVRNodeData() : nullptr;
    if (!player || !vr) {
        SKSE::log::warn("ChainMorningstarVR: global READ-ONLY VRMeleeData probe skipped: player VR nodes unavailable");
        return;
    }

    struct HandCandidate {
        const char* name;
        std::size_t offset;
        RE::NiAVObject* expectedOffsetNode;
    };
    const HandCandidate hands[] = {
        {"right", kPlanckRightVRMeleeDataOffset, vr->RightMeleeWeaponOffsetNode.get()},
        {"left",  kPlanckLeftVRMeleeDataOffset,  vr->LeftMeleeWeaponOffsetNode.get()}
    };

    const auto base = reinterpret_cast<std::uintptr_t>(player);
    for (const auto& hand : hands) {
        const auto raw = readNativeMeleeSnapshot(base + hand.offset);
        const auto expected = reinterpret_cast<std::uintptr_t>(hand.expectedOffsetNode);
        const auto result = inspectNativeMeleeDataReadOnly(raw, expected);
        SKSE::log::info(
            "ChainMorningstarVR: GLOBAL READ-ONLY {} VRMeleeData status={}({}) candidate=0x{:X} world=0x{:X} collision=0x{:X} offset=0x{:X} offsetKnownAs={} expectedOffset=0x{:X} expectedMatch={} threshold={:.3f} enable={} impulse={} swing={} cooldown={:.3f} duration={:.3f}",
            hand.name,
            static_cast<unsigned>(result.status),
            nativeMeleeProbeStatusName(result.status),
            base + hand.offset,
            result.world,
            result.collisionNode,
            result.offsetNode,
            identifyKnownVrOffsetNode(vr, result.offsetNode),
            expected,
            result.offsetMatchesExpected,
            result.linearVelocityThreshold,
            result.enableCollision,
            result.applyImpulseOnHit,
            result.swingDirection,
            result.cooldown,
            result.duration);
    }
#else
    SKSE::log::debug("ChainMorningstarVR: global VRMeleeData probe disabled in release build");
#endif
}

RE::NiAVObject* SkyrimVRSceneBridge::findUnder(RE::NiAVObject* root, std::string_view name) const
{
    if (!root) return nullptr;
    return root->GetObjectByName(RE::BSFixedString{name.data()});
}

Vec3 SkyrimVRSceneBridge::toCms(const RE::NiPoint3& p) { return {p.x,p.y,p.z}; }
RE::NiPoint3 SkyrimVRSceneBridge::toNi(Vec3 p) { return {p.x,p.y,p.z}; }

Mat3 SkyrimVRSceneBridge::toCms(const RE::NiMatrix3& m)
{
    Mat3 out{};
    for (int r=0;r<3;++r) for (int c=0;c<3;++c) out.m[r][c]=m.entry[r][c];
    return out;
}

RE::NiMatrix3 SkyrimVRSceneBridge::toNi(const Mat3& m)
{
    RE::NiMatrix3 out{};
    for (int r=0;r<3;++r) for (int c=0;c<3;++c) out.entry[r][c]=m.m[r][c];
    return out;
}

RigidTransform SkyrimVRSceneBridge::anchorWorldTransformSU() const
{
    RigidTransform out{};
    if (!anchor_) return out;
    out.translation=toCms(anchor_->world.translate);
    out.rotation=toCms(anchor_->world.rotate);
    out.scale=anchor_->world.scale;
    return out;
}

bool SkyrimVRSceneBridge::reacquireWeaponNodes()
{
    releaseWeaponNodes();
    auto* player=RE::PlayerCharacter::GetSingleton();
    if (!player || !player->IsWeaponDrawn() || !player->GetParentCell()) return false;
    auto* vr=player->GetVRNodeData();
    if (!vr) return false;

    struct Candidate { RE::NiAVObject* root; bool left; };
    const Candidate candidates[] = {
        {vr->RightMeleeWeaponOffsetNode.get(), false},
        {vr->LeftMeleeWeaponOffsetNode.get(), true}
    };

    for (const auto& c : candidates) {
        if (!c.root) continue;
        auto* candidateAnchor=findUnder(c.root,kChainAnchorNode);
        if (!candidateAnchor) continue;
        meleeRoot_.reset(c.root);
        anchor_.reset(candidateAnchor);
        isLeftHand_=c.left;
        ownerPlayerAddress_=reinterpret_cast<std::uintptr_t>(player);
        ownerCellAddress_=reinterpret_cast<std::uintptr_t>(player->GetParentCell());
        break;
    }
    if (!anchor_) {
        releaseWeaponNodes();
        return false;
    }

    for (std::size_t i=0;i<links_.size();++i) {
        links_[i].reset(findUnder(anchor_.get(), kLinkNodes[i]));
        if (!links_[i] || links_[i]->parent != anchor_.get()) {
            SKSE::log::error("ChainMorningstarVR: missing runtime link node or unexpected parent: {}", kLinkNodes[i]);
            releaseWeaponNodes();
            return false;
        }
    }
    head_.reset(findUnder(anchor_.get(), kHeadNode));
    if (!head_ || head_->parent != anchor_.get()) {
        SKSE::log::error("ChainMorningstarVR: missing head node or unexpected parent: {}", kHeadNode);
        releaseWeaponNodes();
        return false;
    }
    SKSE::log::info("ChainMorningstarVR: acquired {}-hand VR scene nodes (14 links + head)", isLeftHand_ ? "left" : "right");
    runReadOnlyNativeMeleeProbe();
    return true;
}

void SkyrimVRSceneBridge::runReadOnlyNativeMeleeProbe()
{
#if defined(CMS_ENABLE_READONLY_VRMELEE_PROBE) && CMS_ENABLE_READONLY_VRMELEE_PROBE
    if (!nativeReadOnlyLayoutSupported()) return;
    auto* player=RE::PlayerCharacter::GetSingleton();
    auto* vr=player ? player->GetVRNodeData() : nullptr;
    if (!player || !vr) return;
    auto* expectedNode = isLeftHand_ ? vr->LeftMeleeWeaponOffsetNode.get() : vr->RightMeleeWeaponOffsetNode.get();
    const auto base=reinterpret_cast<std::uintptr_t>(player);
    const auto offset=isLeftHand_ ? kPlanckLeftVRMeleeDataOffset : kPlanckRightVRMeleeDataOffset;
    const auto raw=readNativeMeleeSnapshot(base+offset);
    const auto expected=reinterpret_cast<std::uintptr_t>(expectedNode);
    const auto result=inspectNativeMeleeDataReadOnly(raw,expected);
    SKSE::log::info(
        "ChainMorningstarVR: READ-ONLY VRMeleeData probe status={}({}) world=0x{:X} collision=0x{:X} offset=0x{:X} offsetKnownAs={} expectedMatch={} threshold={:.3f} swing={} cooldown={:.3f} duration={:.3f}",
        static_cast<unsigned>(result.status), nativeMeleeProbeStatusName(result.status),
        result.world, result.collisionNode, result.offsetNode,
        identifyKnownVrOffsetNode(vr, result.offsetNode), result.offsetMatchesExpected,
        result.linearVelocityThreshold, result.swingDirection, result.cooldown, result.duration);
    if (!result.plausible()) {
        SKSE::log::warn("ChainMorningstarVR: native melee layout probe rejected candidate; no native proxy writes enabled");
    }
#endif
}

bool SkyrimVRSceneBridge::currentHandStillOwnsAnchor() const
{
    if (!anchor_ || !head_ || head_->parent != anchor_.get()) return false;
    for (const auto& link : links_) {
        if (!link || link->parent != anchor_.get()) return false;
    }

    auto* player = RE::PlayerCharacter::GetSingleton();
    auto* vr = player ? player->GetVRNodeData() : nullptr;
    if (!player || !vr || !player->IsWeaponDrawn() ||
        reinterpret_cast<std::uintptr_t>(player) != ownerPlayerAddress_ ||
        reinterpret_cast<std::uintptr_t>(player->GetParentCell()) != ownerCellAddress_) return false;

    RE::NiAVObject* currentRoot = isLeftHand_
        ? static_cast<RE::NiAVObject*>(vr->LeftMeleeWeaponOffsetNode.get())
        : static_cast<RE::NiAVObject*>(vr->RightMeleeWeaponOffsetNode.get());
    if (!currentRoot) return false;

    // A retained NiPointer can keep a detached old weapon graph alive after unequip.
    // Identity under the CURRENT hand root is therefore the authoritative ownership test.
    auto* currentAnchor = findUnder(currentRoot, kChainAnchorNode);
    return currentAnchor == anchor_.get();
}

void SkyrimVRSceneBridge::releaseWeaponNodes()
{
    for (auto& sound : chainSounds_) {
        if (sound.soundID != RE::BSSoundHandle::kInvalidID) sound.Stop();
        sound = RE::BSSoundHandle{};
    }
    nextChainSound_ = 0;
    ownerPlayerAddress_ = 0;
    ownerCellAddress_ = 0;
    head_.reset();
    for (auto& n:links_) n.reset();
    anchor_.reset();
    meleeRoot_.reset();
    isLeftHand_=false;
    readOnlyNativeMotionStateKnown_=false;
    readOnlyNativeProbeRejectedWarned_=false;
    readOnlyNativeEnableCollision_=false;
    readOnlyNativeSwingDirection_=0;
    readOnlyNativeCollisionNode_=0;
}

bool SkyrimVRSceneBridge::tryGetChainAnchorWorldSU(Vec3& outPositionSU, Vec3& outInitialDirectionWorld)
{
    if (!anchor_ || !currentHandStillOwnsAnchor()) {
        return false;
    }
    const RigidTransform t=anchorWorldTransformSU();
    if (!isFinite(t.translation) || !std::isfinite(t.scale) || t.scale <= 1.0e-6f ||
        !approximatelyOrthonormal(t.rotation, 0.02f)) return false;
    outPositionSU=t.translation;
    outInitialDirectionWorld=normalized(mul(t.rotation,Vec3{0,0,1}));
    return true;
}

void SkyrimVRSceneBridge::writeNodeWorldPose(RE::NiAVObject* node, Vec3 centerWorldM, Vec3 localZWorld, float rollRadians)
{
    if (!node || !anchor_) return;
    const RigidTransform parent=anchorWorldTransformSU();
    const Vec3 centerWorldSU=centerWorldM*kSkyrimUnitsPerMeter;
    node->local.translate=toNi(worldToLocalPoint(parent,centerWorldSU));
    const Mat3 worldR=basisFromLocalZ(localZWorld,rollRadians);
    node->local.rotate=toNi(worldToLocalRotation(parent,worldR));
    node->local.scale=1.0f;
}

void SkyrimVRSceneBridge::applyVisualFrame(const VisualFrame& frame)
{
    if (!visualNodesReady() || !currentHandStillOwnsAnchor() || frame.links.size()!=links_.size()) return;
    if (!isFinite(frame.head.centerM) || !isFinite(frame.head.chainAxis)) return;
    for (const auto& link : frame.links) {
        if (!isFinite(link.centerM) || !isFinite(link.tangent) || !std::isfinite(link.rollRadians)) return;
    }
    for (std::size_t i=0;i<links_.size();++i)
        writeNodeWorldPose(links_[i].get(),frame.links[i].centerM,frame.links[i].tangent,frame.links[i].rollRadians);
    writeNodeWorldPose(head_.get(),frame.head.centerM,frame.head.chainAxis,0.0f);

    // PlayerCharacter::Update has already run. Refresh the owned subtree after
    // writing local poses so visuals do not lag a frame behind their simulation.
    RE::NiUpdateData updateData{};
    updateData.time = 0.0f;
    anchor_->Update(updateData);
}

bool SkyrimVRSceneBridge::updateNativeMeleeHeadProxy(const HeadSweep& sweep)
{
#if defined(CMS_ENABLE_READONLY_VRMELEE_PROBE) && CMS_ENABLE_READONLY_VRMELEE_PROBE
    if (!nativeReadOnlyLayoutSupported()) return false;
    auto* player = RE::PlayerCharacter::GetSingleton();
    if (!player || !anchor_ || !currentHandStillOwnsAnchor()) {
        return false;
    }

    const auto base = reinterpret_cast<std::uintptr_t>(player);
    const auto offset = isLeftHand_ ? kPlanckLeftVRMeleeDataOffset : kPlanckRightVRMeleeDataOffset;
    const auto raw = readNativeMeleeSnapshot(base + offset);
    const auto probe = inspectNativeMeleeDataReadOnly(raw, 0);

    if (!probe.plausible()) {
        if (!readOnlyNativeProbeRejectedWarned_) {
            SKSE::log::warn(
                "ChainMorningstarVR: READ-ONLY MOTION probe rejected {} hand VRMeleeData status={}({}); no writes performed",
                isLeftHand_ ? "left" : "right",
                static_cast<unsigned>(probe.status),
                nativeMeleeProbeStatusName(probe.status));
            readOnlyNativeProbeRejectedWarned_ = true;
        }
        return false;
    }

    readOnlyNativeProbeRejectedWarned_ = false;
    const bool stateChanged =
        !readOnlyNativeMotionStateKnown_ ||
        readOnlyNativeEnableCollision_ != probe.enableCollision ||
        readOnlyNativeSwingDirection_ != probe.swingDirection ||
        readOnlyNativeCollisionNode_ != probe.collisionNode;

    if (stateChanged) {
        SKSE::log::info(
            "ChainMorningstarVR: READ-ONLY MOTION hand={} headSpeedMps={:.3f} nativeEnable={} nativeSwing={} collision=0x{:X} threshold={:.3f} cooldown={:.3f} duration={:.3f}",
            isLeftHand_ ? "left" : "right",
            sweep.speedMps,
            probe.enableCollision,
            probe.swingDirection,
            probe.collisionNode,
            probe.linearVelocityThreshold,
            probe.cooldown,
            probe.duration);
    }

    readOnlyNativeMotionStateKnown_ = true;
    readOnlyNativeEnableCollision_ = probe.enableCollision;
    readOnlyNativeSwingDirection_ = probe.swingDirection;
    readOnlyNativeCollisionNode_ = probe.collisionNode;
    return false;
#else
    if (!warnedNativeProxy_) {
        SKSE::log::warn(
            "ChainMorningstarVR: native moving melee proxy is disabled in this build; visual bridge only");
        warnedNativeProxy_=true;
    }
    return false;
#endif
}

float SkyrimVRSceneBridge::consumeWorldContactImpulse() { return 0.0f; }
void SkyrimVRSceneBridge::playChainSound(float intensity)
{
    if (!head_ || !currentHandStillOwnsAnchor() || !std::isfinite(intensity) || intensity <= 0.0f) return;
    // Verified against the user's Skyrim.esm SNDR_0003D128 record: PHYChainSD.
    // It chooses among four native physics-chain samples. No sound assets are bundled.
    constexpr RE::FormID kPhysicsChainSoundID = 0x0003D128;
    auto* descriptor = RE::TESForm::LookupByID<RE::BGSSoundDescriptorForm>(kPhysicsChainSoundID);
    auto* audio = RE::BSAudioManager::GetSingleton();
    if (!descriptor || !audio) {
        if (!warnedChainSound_) {
            SKSE::log::warn("ChainMorningstarVR: native PHYChainSD or audio manager unavailable");
            warnedChainSound_ = true;
        }
        return;
    }

    // Bound overlapping one-shots, and stop them explicitly on unequip/load.
    auto& sound = chainSounds_[nextChainSound_];
    nextChainSound_ = (nextChainSound_ + 1) % chainSounds_.size();
    if (sound.soundID != RE::BSSoundHandle::kInvalidID) sound.Stop();
    sound = RE::BSSoundHandle{};
    if (!audio->BuildSoundDataFromDescriptor(sound, descriptor, 0x10) ||
        sound.soundID == RE::BSSoundHandle::kInvalidID) return;
    sound.SetPosition(head_->world.translate);
    sound.SetObjectToFollow(head_.get());
    sound.SetVolume(std::clamp(intensity, 0.0f, 1.0f));
    sound.Play();
}

void SkyrimVRSceneBridge::playChainRattle(float intensity) { playChainSound(intensity); }
void SkyrimVRSceneBridge::playChainClank(float intensity) { playChainSound(intensity); }

} // namespace cms::skyrimvr
