#include "SkyrimVRSceneBridge.hpp"
#include <SKSE/SKSE.h>

namespace cms::skyrimvr {

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
    if (std::fabs(out.scale)<1.0e-6f) out.scale=1.0f;
    return out;
}

bool SkyrimVRSceneBridge::reacquireWeaponNodes()
{
    releaseWeaponNodes();
    auto* player=RE::PlayerCharacter::GetSingleton();
    if (!player) return false;
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
        meleeRoot_=c.root;
        anchor_=candidateAnchor;
        isLeftHand_=c.left;
        break;
    }
    if (!anchor_) {
        releaseWeaponNodes();
        return false;
    }

    for (std::size_t i=0;i<links_.size();++i) {
        links_[i]=findUnder(anchor_.get(), kLinkNodes[i]);
        if (!links_[i]) {
            SKSE::log::error("ChainMorningstarVR: missing runtime link node {}", kLinkNodes[i]);
            releaseWeaponNodes();
            return false;
        }
    }
    head_=findUnder(anchor_.get(), kHeadNode);
    if (!head_) {
        SKSE::log::error("ChainMorningstarVR: missing {}", kHeadNode);
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
    auto* player=RE::PlayerCharacter::GetSingleton();
    auto* vr=player ? player->GetVRNodeData() : nullptr;
    if (!player || !vr) return;
    auto* expectedNode = isLeftHand_ ? vr->LeftMeleeWeaponOffsetNode.get() : vr->RightMeleeWeaponOffsetNode.get();
    if (!expectedNode) return;
    const auto base=reinterpret_cast<std::uintptr_t>(player);
    const auto offset=isLeftHand_ ? kPlanckLeftVRMeleeDataOffset : kPlanckRightVRMeleeDataOffset;
    const auto* raw=reinterpret_cast<const NativeVRMeleeDataProbeLayout*>(base+offset);
    const auto expected=reinterpret_cast<std::uintptr_t>(expectedNode);
    const auto result=inspectNativeMeleeDataReadOnly(*raw,expected);
    SKSE::log::info(
        "ChainMorningstarVR: READ-ONLY VRMeleeData probe status={} world=0x{:X} collision=0x{:X} offset=0x{:X} threshold={:.3f}",
        static_cast<unsigned>(result.status), result.world, result.collisionNode, result.offsetNode, result.linearVelocityThreshold);
    if (!result.plausible()) {
        SKSE::log::warn("ChainMorningstarVR: native melee layout probe rejected candidate; no native proxy writes enabled");
    }
#endif
}

void SkyrimVRSceneBridge::releaseWeaponNodes()
{
    head_.reset();
    for (auto& n:links_) n.reset();
    anchor_.reset();
    meleeRoot_.reset();
    isLeftHand_=false;
}

bool SkyrimVRSceneBridge::tryGetChainAnchorWorldSU(Vec3& outPositionSU, Vec3& outInitialDirectionWorld)
{
    if (!anchor_) return false;
    const RigidTransform t=anchorWorldTransformSU();
    outPositionSU=t.translation;
    outInitialDirectionWorld=normalized(mul(t.rotation,{0,0,1}));
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
    if (!visualNodesReady() || frame.links.size()!=links_.size()) return;
    for (std::size_t i=0;i<links_.size();++i)
        writeNodeWorldPose(links_[i].get(),frame.links[i].centerM,frame.links[i].tangent,frame.links[i].rollRadians);
    writeNodeWorldPose(head_.get(),frame.head.centerM,frame.head.chainAxis,0.0f);
}

bool SkyrimVRSceneBridge::updateNativeMeleeHeadProxy(const HeadSweep&)
{
    if (!warnedNativeProxy_) {
        SKSE::log::warn("ChainMorningstarVR: native moving melee proxy is NOT enabled in v0.4-dev; visual bridge only");
        warnedNativeProxy_=true;
    }
    return false;
}

float SkyrimVRSceneBridge::consumeWorldContactImpulse() { return 0.0f; }
void SkyrimVRSceneBridge::playChainRattle(float) {}
void SkyrimVRSceneBridge::playChainClank(float) {}

} // namespace cms::skyrimvr
