#include "SkyrimVRSceneBridge.hpp"
#include "NativePhysicsBackend.hpp"
#include "OffhandInput.hpp"
#include "VRFrameContext.hpp"
#include <SKSE/SKSE.h>

namespace cms::skyrimvr {
namespace {
struct BodyPart { const char* a; const char* b; float radius; };
constexpr BodyPart bodyParts[]={
    {"NPC Pelvis [Pelv]","NPC Spine1 [Spn1]",.145f},
    {"NPC Spine1 [Spn1]","NPC Spine2 [Spn2]",.17f},
    {"NPC Neck [Neck]","NPC Head [Head]",.105f},
    {"NPC L UpperArm [LUar]","NPC L Forearm [LLar]",.055f},
    {"NPC L Forearm [LLar]","NPC L Hand [LHnd]",.045f},
    {"NPC R UpperArm [RUar]","NPC R Forearm [RLar]",.055f},
    {"NPC R Forearm [RLar]","NPC R Hand [RHnd]",.045f},
    {"NPC L Thigh [LThg]","NPC L Calf [LClf]",.08f},
    {"NPC L Calf [LClf]","NPC L Foot [Lft ]",.055f},
    {"NPC R Thigh [RThg]","NPC R Calf [RClf]",.08f},
    {"NPC R Calf [RClf]","NPC R Foot [Rft ]",.055f}
};
}

void SkyrimVRSceneBridge::resetPlayerInteraction() {
    ResetOffhandInput();offhandGrab_.reset();playerCapsules_.clear();
    playerBodyContacts_=0;reportedPlayerBody_=false;grabSamples_=bodyContactSamples_=0;
    gripAttemptSamples_=0;gripWasDown_=false;
}

HeadHoldTarget SkyrimVRSceneBridge::updatePlayerInteraction(const HeadPose& head,Vec3 anchorM,float dt) {
    if (!currentHandStillOwnsAnchor()||!std::isfinite(dt)||dt<=0) {
        resetPlayerInteraction();return {};
    }
    auto* player=RE::PlayerCharacter::GetSingleton();
    // The already-certified visible VRIK skeleton supplies body positions.
    // No PlayerCharacter collision node/filter or capsule is changed.
    std::vector<BodyCapsule> current;
    if (!firstPerson_) {
        current.reserve(std::size(bodyParts));
        for (std::size_t i=0;i<std::size(bodyParts);++i) {
            const auto& part=bodyParts[i];
            auto* a=findUnder(sceneRoot_.get(),part.a);
            auto* b=findUnder(sceneRoot_.get(),part.b);
            if (!a||!b) continue;
            const float scale=a->world.scale;
            const Vec3 start=toCms(a->world.translate)*kMetersPerSkyrimUnit;
            const Vec3 end=toCms(b->world.translate)*kMetersPerSkyrimUnit;
            if (!isFinite(start)||!isFinite(end)||!std::isfinite(scale)||scale<.25f||scale>3||
                length(end-start)>1.2f||length(start-anchorM)>3.5f) continue;
            BodyCapsule capsule{start,end,start,end,part.radius*scale,i+1};
            const auto old=std::find_if(playerCapsules_.begin(),playerCapsules_.end(),
                [&](const auto& value){return value.identity==capsule.identity;});
            if (old!=playerCapsules_.end()&&dt<=.05f&&
                length(old->a-start)<.5f&&length(old->b-end)<.5f) {
                capsule.previousA=old->a;capsule.previousB=old->b;
            }
            current.push_back(capsule);
        }
    }
    playerCapsules_=std::move(current);playerBodyDt_=dt;
    if (!reportedPlayerBody_) {
        reportedPlayerBody_=true;
        SKSE::log::info("CMS player-body chain collision: capsules={} source={} damage=false",
            playerCapsules_.size(),firstPerson_?"unavailable without VRIK body":"visible VRIK skeleton");
    }

    auto* hand=findUnder(sceneRoot_.get(),"NPC L Hand [LHnd]");
    const char* blocked=isLeftHand_?"weapon-in-left-hand":!hand?"left-hand-node-missing":
        player->GetEquippedObject(InventoryLeftHand(true))?"left-hand-equipped":
        NativePhysicsBackend::GetSingleton().LeftHandBlockReason();
    const bool freeHand=blocked==nullptr;
    RigidTransform palm{};
    if (hand) {
        palm.translation=toCms(hand->world.translate)*kMetersPerSkyrimUnit;
        palm.rotation=toCms(hand->world.rotate);
        // Midpoint from wrist to middle-finger base approximates the visible
        // palm without assuming HIGGS's user-configurable local hand offsets.
        auto* finger=findUnder(hand,"NPC L Finger20 [LF20]");
        if (finger) {
            const Vec3 base=toCms(finger->world.translate)*kMetersPerSkyrimUnit;
            if (isFinite(base)&&length(base-palm.translation)<.20f)
                palm.translation=lerp(palm.translation,base,.5f);
        }
    }
    const auto input=ReadLeftGrip();
    const bool wasHeld=offhandGrab_.held();
    const float radius=kHeadBroadphaseRadiusM*acquiredScale_;
    const auto hold=offhandGrab_.update(input.fresh,input.down,input.captured,freeHand,
        palm,head.centerM,anchorM,radius,kStraightReachM,dt);
    const bool nearHead=freeHand&&isFinite(palm.translation)&&
        length(palm.translation-head.centerM)<=radius+.06f;
    if(input.fresh&&input.down&&!gripWasDown_&&gripAttemptSamples_<16) {
        ++gripAttemptSamples_;
        SKSE::log::info("CMS offhand grip attempt: result={} reason={} distanceM={} captured={}",
            hold.active?"held":"rejected",hold.active?"ready":blocked?blocked:
            !nearHead?"outside-head-reach":!input.captured?"press-not-armed":"pose-or-chain-limit",
            hand?length(palm.translation-head.centerM):-1.f,input.captured);
    }
    gripWasDown_=input.down;
    // Arm a fresh press only. Captured holds keep the grip until released.
    ArmLeftGrip(freeHand&&(hold.active||(nearHead&&!input.down)));
    if (wasHeld!=hold.active&&grabSamples_<12) {
        ++grabSamples_;
        SKSE::log::info("CMS offhand head grip: {} physical-left=true right-weapon=true",
            hold.active?"held":"released");
    }
    return hold;
}
} // namespace cms::skyrimvr
