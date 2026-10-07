#include "SkyrimVRSceneBridge.hpp"
#include "PlanckBuildProbe.hpp"
#include "NativePhysicsBackend.hpp"
#include "NativeContactRouter.hpp"
#include "WeaponMeshContact.hpp"
#include "VRFrameContext.hpp"
#include "../EquippedSceneCore.hpp"
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
    auto* data = RE::TESDataHandler::GetSingleton();
    auto* cmsWeapon = data ? data->LookupForm<RE::TESObjectWEAP>(0x800, "ChainMorningstarVR.esp") : nullptr;
    if (!cmsWeapon) return false;
    // Same visible skeleton and WEAPON/SHIELD slots as HIGGS Hand::GetWeaponNode.
    // MeleeWeaponOffsetNode is a collision offset, not the equipped model root.
    const bool firstPerson = GetModuleHandle("vrik.dll") == nullptr;
    auto* scene = player->Get3D(firstPerson);
    std::uint32_t failure = scene ? 1u : 2u;
    bool equipped = false;
    for (bool inventoryLeft : {false, true}) {
        if (player->GetEquippedObject(inventoryLeft) != cmsWeapon) continue;
        equipped = true;
        const auto graph = findEquippedChainGraph(scene, inventoryLeft,
            [this](RE::NiAVObject* node, std::string_view name){ return findUnder(node, name); },
            [](RE::NiAVObject* node) -> RE::NiAVObject* { return node->parent; });
        auto* slot = graph.slot;
        auto* model = graph.model;
        auto* candidateAnchor = graph.anchor;
        failure |= (slot ? 4u : 8u) | (model ? 16u : 32u);
        if (!candidateAnchor || candidateAnchor->parent != model) continue;
        sceneRoot_.reset(scene);
        weaponSlot_.reset(slot);
        weaponRoot_.reset(model);
        anchor_.reset(candidateAnchor);
        inventoryLeft_ = inventoryLeft;
        acquiredLeftMode_ = VRLeftHandedMode();
        isLeftHand_ = inventoryLeft != acquiredLeftMode_;
        firstPerson_ = firstPerson;
        ownerPlayerAddress_=reinterpret_cast<std::uintptr_t>(player);
        ownerCellAddress_=reinterpret_cast<std::uintptr_t>(player->GetParentCell());
        break;
    }
    if (!anchor_) {
        if (equipped && failure != lastAcquireFailure_) {
            SKSE::log::warn("CMS equipped but attached model unavailable: view={} scene={} details={} anchorElsewhere={}; check NIF Prn=WeaponMace and draw state",
                firstPerson ? "first-person" : "VRIK third-person", scene != nullptr, failure,
                findUnder(scene, kChainAnchorNode) != nullptr);
        }
        lastAcquireFailure_ = equipped ? failure : 0;
        return false;
    }
    lastAcquireFailure_ = 0;

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
    SKSE::log::info("ChainMorningstarVR: acquired {}-hand VR scene nodes ({} links + head); view={} slot={} root={} scale={}",
        isLeftHand_ ? "left" : "right", kChainLinkCount, firstPerson_ ? "first-person" : "VRIK third-person",
        inventoryLeft_ ? "SHIELD" : "WEAPON", weaponRoot_->name.c_str(), anchor_->world.scale);
    SKSE::log::info("ChainMorningstarVR: native weapon-blood surfaces fx={} lighting={} parent=CMS_HeadNode; visibility owned by game",
        findUnder(head_.get(), "BloodFX") != nullptr, findUnder(head_.get(), "BloodLighting") != nullptr);
    diagnosticAnchor_ = toCms(anchor_->world.translate);
    if (++nativeGeneration_ == 0) ++nativeGeneration_;
    acquiredScale_ = anchor_->world.scale;
    auto& native = NativePhysicsBackend::GetSingleton();
    nativePrepared_ = native.BeginSession(weaponRoot_.get(), isLeftHand_, nativeGeneration_);
    nativePrepareRetries_ = !nativePrepared_ && native.Available() ? 3 : 0;
    nativePrepareCooldownS_ = 0.5f;
    if (!nativePrepared_) SKSE::log::warn("Native head preparation pending/unavailable; retries={}", nativePrepareRetries_);
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
    if (!player || !player->IsWeaponDrawn() ||
        reinterpret_cast<std::uintptr_t>(player) != ownerPlayerAddress_ ||
        reinterpret_cast<std::uintptr_t>(player->GetParentCell()) != ownerCellAddress_ ||
        VRLeftHandedMode() != acquiredLeftMode_) return false;
    auto* data = RE::TESDataHandler::GetSingleton();
    auto* cmsWeapon = data ? data->LookupForm<RE::TESObjectWEAP>(0x800, "ChainMorningstarVR.esp") : nullptr;
    if (!cmsWeapon || player->GetEquippedObject(inventoryLeft_) != cmsWeapon) return false;
    auto* scene = player->Get3D(firstPerson_);
    if (!scene || scene != sceneRoot_.get()) return false;
    auto* slot = findUnder(scene, inventoryLeft_ ? "SHIELD" : "WEAPON");
    if (!slot || slot != weaponSlot_.get()) return false;
    // A retained NiPointer can keep a detached old graph alive. Certify identity
    // below the CURRENT equipped slot, never merely below the whole player.
    auto* currentAnchor = findUnder(slot, kChainAnchorNode);
    return currentAnchor == anchor_.get() && currentAnchor->parent == weaponRoot_.get();
}

void SkyrimVRSceneBridge::releaseWeaponNodes()
{
    resetPlayerInteraction();
    NativePhysicsBackend::GetSingleton().EndSession();
    WeaponMeshContact::GetSingleton().Reset();
    nativePrepared_ = false;
    nativePrepareRetries_ = 0;
    nativePrepareCooldownS_ = 0.0f;
    for (auto& sound : chainSounds_) {
        if (sound.soundID != RE::BSSoundHandle::kInvalidID) sound.Stop();
        sound = RE::BSSoundHandle{};
    }
    for (auto& sound : impactSounds_) {
        if (sound.soundID != RE::BSSoundHandle::kInvalidID) sound.Stop();
        sound = RE::BSSoundHandle{};
    }
    nextChainSound_ = 0;
    nextImpactSound_ = 0;
    impactSoundSamples_ = 0;
    ownerPlayerAddress_ = 0;
    ownerCellAddress_ = 0;
    head_.reset();
    for (auto& n:links_) n.reset();
    anchor_.reset();
    weaponRoot_.reset();
    weaponSlot_.reset();
    sceneRoot_.reset();
    diagnosticsTime_ = 0;
    diagnosticSamples_ = 0;
    diagnosticMaxTravelM_ = 0;
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
    // A VRIK/model scale change invalidates the cloned collision shape too.
    if (std::fabs(t.scale - acquiredScale_) > 0.001f * acquiredScale_) return false;
    outPositionSU=t.translation;
    outInitialDirectionWorld=normalized(mul(t.rotation,Vec3{0,0,1}));
    return true;
}

void SkyrimVRSceneBridge::writeNodeWorldPose(RE::NiAVObject* node, Vec3 centerWorldM, const Mat3& worldR)
{
    if (!node || !anchor_) return;
    const RigidTransform parent=anchorWorldTransformSU();
    const Vec3 centerWorldSU=centerWorldM*kSkyrimUnitsPerMeter;
    node->local.translate=toNi(worldToLocalPoint(parent,centerWorldSU));
    node->local.rotate=toNi(worldToLocalRotation(parent,worldR));
    node->local.scale=1.0f;
}

void SkyrimVRSceneBridge::applyVisualFrame(const VisualFrame& frame)
{
    if (!visualNodesReady() || !currentHandStillOwnsAnchor() || frame.links.size()!=links_.size()) return;
    if (!isFinite(frame.head.centerM) || !approximatelyOrthonormal(frame.head.rotation, .01f)) return;
    for (const auto& link : frame.links) {
        if (!isFinite(link.centerM) || !isFinite(link.tangent) || !std::isfinite(link.rollRadians)) return;
    }
    for (std::size_t i=0;i<links_.size();++i)
        writeNodeWorldPose(links_[i].get(),frame.links[i].centerM,frame.links[i].rotation);
    writeNodeWorldPose(head_.get(),frame.head.centerM,frame.head.rotation);

    // HIGGS/VRIK have updated tracked hands. Refresh the owned subtree after
    // writing local poses so visuals do not lag a frame behind their simulation.
    RE::NiUpdateData updateData{};
    updateData.time = 0.0f;
    anchor_->Update(updateData);
    lastVisualHeadErrorM_=length(toCms(head_->world.translate)*kMetersPerSkyrimUnit-frame.head.centerM);
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
    (void)sweep;
    return false;
#endif
}

void SkyrimVRSceneBridge::submitNativePose(const HeadPose& pose, const HeadSweep& sweep, float frameDt)
{
    if (!currentHandStillOwnsAnchor()) return;
    auto& native = NativePhysicsBackend::GetSingleton();
    if (!nativePrepared_ && nativePrepareRetries_) {
        nativePrepareCooldownS_ -= frameDt;
        if (nativePrepareCooldownS_ <= 0.0f) {
            --nativePrepareRetries_;
            nativePrepareCooldownS_ = 0.5f;
            nativePrepared_ = native.BeginSession(weaponRoot_.get(), isLeftHand_, nativeGeneration_);
            if (!nativePrepared_ && !nativePrepareRetries_)
                SKSE::log::warn("Native head preparation failed after bounded retries; re-equip after resolving dependencies/shape warnings");
        }
    }
    native.SubmitPose(pose, frameDt);
    auto* player = RE::PlayerCharacter::GetSingleton();
    auto* weapon = player ? player->GetEquippedObject(inventoryLeft_) : nullptr;
    const auto snapshot = native.Snapshot();
    WeaponMeshContact::GetSingleton().Update(snapshot, frameDt, weapon ? weapon->GetFormID() : 0);
    // Three bounded samples per equip: prove movement and collider readiness,
    // without logging controller coordinates or flooding the user's logs.
    if (diagnosticSamples_ < 3) {
        diagnosticMaxTravelM_ = std::max(diagnosticMaxTravelM_,
            length(toCms(anchor_->world.translate) - diagnosticAnchor_) / kSkyrimUnitsPerMeter);
        diagnosticsTime_ += frameDt;
        if (diagnosticsTime_ >= 5.0f) {
            SKSE::log::info("CMS tracking sample: hand={} anchorTravelM={:.3f} headSpeedMps={:.3f} nativePrepared={} colliderReady={} physicsStep={} chainSweeps={} chainContacts={} playerBodyContacts={} offhandHeld={}",
                isLeftHand_ ? "left" : "right", diagnosticMaxTravelM_, sweep.speedMps,
                nativePrepared_, snapshot.ready, snapshot.physicsStep,snapshot.chainSweeps,snapshot.chainContacts,
                playerBodyContacts_,offhandGrab_.held());
            ++diagnosticSamples_;
            diagnosticsTime_ = 0;
        }
    }
#if defined(CMS_ENABLE_READONLY_VRMELEE_PROBE) && CMS_ENABLE_READONLY_VRMELEE_PROBE
    updateNativeMeleeHeadProxy(sweep);
#else
    (void)sweep;
#endif
}

std::vector<HeadWorldContact> SkyrimVRSceneBridge::consumeWorldContacts()
{
    NativeContactRouter::GetSingleton().DrainAndRefresh();
    return NativePhysicsBackend::GetSingleton().ConsumeContacts();
}

void SkyrimVRSceneBridge::queryChainContacts(const std::vector<ChainLinkSweep>& sweeps,
                                            std::vector<ChainLinkContact>& contacts)
{
    if (!currentHandStillOwnsAnchor()) return;
    const auto before=contacts.size();
    queryPlayerBodyContacts(sweeps,playerCapsules_,playerBodyDt_,contacts);
    playerBodyContacts_+=contacts.size()-before;
    if (contacts.size()>before&&bodyContactSamples_<3) {
        ++bodyContactSamples_;
        SKSE::log::info("CMS player-body chain contact: samples={} total={} damage=false",contacts.size()-before,playerBodyContacts_);
    }
    // The player's motion is swept once per render sample. Subsequent fixed
    // steps/reconciliation queries use the current capsules, not repeated motion.
    for (auto& b:playerCapsules_) {b.previousA=b.a;b.previousB=b.b;}
    NativePhysicsBackend::GetSingleton().QueryChainContacts(sweeps,contacts);
}

float SkyrimVRSceneBridge::consumeWorldContactImpulse() { return 0.0f; }
void SkyrimVRSceneBridge::playChainSound(float intensity, bool heavyImpact)
{
    if (!head_ || !currentHandStillOwnsAnchor() || !std::isfinite(intensity) || intensity <= 0.0f) return;
    intensity = std::clamp(intensity, 0.0f, 1.0f);
    struct Layer {
        RE::BGSSoundDescriptorForm* descriptor{};
        const char* name{};
        float volume{};
    };
    std::array<Layer, 2> layers{};
    const std::size_t layerCount = heavyImpact ? 2 : 1;
    if (heavyImpact) {
        // 0.8.0 logs accept PHYGenericMetalHeavy at full volume but the user
        // cannot distinguish it. Use two DIFFERENT cues, grounded in the user's
        // Skyrim.esm records: large metal body (loud NAM1 0009150C) and blunt
        // metal strike (SNAM 0003C826). Only descriptors are played: no impact
        // effect, sparks, damage or world object is spawned by this audio path.
        layers[0] = {nullptr, "large-metal-body", .75f + .25f * intensity};
        layers[1] = {nullptr, "blunt-metal-strike", .48f + .18f * intensity};
        if (auto* impact = RE::TESForm::LookupByID<RE::BGSImpactData>(0x0009150E))
            layers[0].descriptor = impact->sound2 ? impact->sound2 : impact->sound1;
        if (auto* impact = RE::TESForm::LookupByID<RE::BGSImpactData>(0x0004BB53))
            layers[1].descriptor = impact->sound1 ? impact->sound1 : impact->sound2;
    } else {
        // PHYChainSD selects from four native chain samples.
        layers[0] = {RE::TESForm::LookupByID<RE::BGSSoundDescriptorForm>(0x0003D128), "chain", intensity};
    }
    auto* audio = RE::BSAudioManager::GetSingleton();
    auto& warned = heavyImpact ? warnedImpactSound_ : warnedChainSound_;
    if (!audio) {
        if (!warned) SKSE::log::warn("ChainMorningstarVR: audio manager unavailable");
        warned = true;
        return;
    }

    // Four paired impacts can decay independently of the four chain rattles.
    // An absent/failed layer still occupies its slot, preserving pair lifetime.
    // Release stops every handle on unequip, load, pause or teleport.
    auto* pool = heavyImpact ? impactSounds_.data() : chainSounds_.data();
    const auto poolSize = heavyImpact ? impactSounds_.size() : chainSounds_.size();
    auto& cursor = heavyImpact ? nextImpactSound_ : nextChainSound_;
    const bool logImpact = heavyImpact && impactSoundSamples_ < 3;
    if (logImpact) ++impactSoundSamples_;
    const auto position = head_->world.translate;
    for (std::size_t i = 0; i < layerCount; ++i) {
        const auto& layer = layers[i];
        auto& sound = pool[cursor];
        cursor = (cursor + 1) % poolSize;
        if (sound.soundID != RE::BSSoundHandle::kInvalidID) sound.Stop();
        sound = RE::BSSoundHandle{};
        const bool built = layer.descriptor &&
            audio->BuildSoundDataFromDescriptor(sound, layer.descriptor, 0x10) &&
            sound.soundID != RE::BSSoundHandle::kInvalidID;
        bool positioned = false, volumeSet = false, played = false;
        if (built) {
            positioned = sound.SetPosition(position);
            if (!heavyImpact) sound.SetObjectToFollow(head_.get());
            volumeSet = sound.SetVolume(layer.volume);
            played = sound.Play();
        }
        if ((!built || !positioned || !volumeSet || !played) && !warned) {
            SKSE::log::warn("ChainMorningstarVR: sound request incomplete layer={} build={} position={} volume={} play={}",
                layer.name, built, positioned, volumeSet, played);
            warned = true;
        }
        if (logImpact) {
            SKSE::log::info("ChainMorningstarVR: heavy-metal impact layer={} descriptor={:08X} volume={:.3f} buildAccepted={} positionAccepted={} volumeAccepted={} playAccepted={}",
                layer.name, layer.descriptor ? layer.descriptor->GetFormID() : 0,
                layer.volume, built, positioned, volumeSet, played);
        }
    }
}

void SkyrimVRSceneBridge::playChainRattle(float intensity) { playChainSound(intensity, false); }
void SkyrimVRSceneBridge::playChainClank(float intensity) { playChainSound(intensity, true); }

} // namespace cms::skyrimvr
