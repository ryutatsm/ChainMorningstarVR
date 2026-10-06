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
    if (offhandGrab_.held()) {
        const auto duration=std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now()-gripStarted_).count();
        SKSE::log::info("CMS offhand head grip: released reason=lifecycle-reset heldMs={} button=left-trigger physical-left=true right-weapon=true",
            duration);
    }
    ResetOffhandInput();offhandGrab_.reset();playerCapsules_.clear();
    playerBodyContacts_=0;reportedPlayerBody_=false;grabSamples_=bodyContactSamples_=0;
    gripAttemptSamples_=0;gripWasDown_=false;
    gripStarted_={};gripProgressSamples_=0;
    gripMaxTargetErrorM_=gripMaxChainExcessM_=0;lastVisualHeadErrorM_=-1;
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
    const auto input=ReadLeftGrab();
    const bool wasHeld=offhandGrab_.held();
    const float radius=kHeadBroadphaseRadiusM*acquiredScale_;
    const auto hold=offhandGrab_.update(input.fresh,input.down,input.captured,freeHand,
        palm,head.centerM,anchorM,radius,kStraightReachM,dt);
    const auto& diagnostic=offhandGrab_.diagnostic();
    const bool nearHead=freeHand&&isFinite(palm.translation)&&
        length(palm.translation-head.centerM)<=radius+.06f;
    const auto now=std::chrono::steady_clock::now();
    if (hold.active&&!wasHeld) {
        gripStarted_=now;gripProgressSamples_=0;
        gripMaxTargetErrorM_=gripMaxChainExcessM_=0;
    }
    if (wasHeld||hold.active) {
        gripMaxTargetErrorM_=std::max(gripMaxTargetErrorM_,diagnostic.targetErrorM);
        gripMaxChainExcessM_=std::max(gripMaxChainExcessM_,diagnostic.chainExcessM);
    }
    const auto heldMs=(wasHeld||hold.active)?
        std::chrono::duration_cast<std::chrono::milliseconds>(now-gripStarted_).count():0;
    if(input.fresh&&input.pressed&&!gripWasDown_&&gripAttemptSamples_<16) {
        ++gripAttemptSamples_;
        SKSE::log::info("CMS offhand grip attempt: result={} reason={} button=left-trigger distanceM={} captured={} radiusM={} inputAgeMs={} inputSerial={} pressed={} touched={} accepted={} visualErrorM={} sideGripPressed={} receivedPressed=0x{:X}",
            hold.active?"held":"rejected",hold.active?"ready":!input.accepted?"input-withdrawn":blocked?blocked:
            !nearHead?"outside-head-reach":!input.captured?"press-not-armed":offhandGrabReasonName(diagnostic.reason),
            hand?length(palm.translation-head.centerM):-1.f,input.captured,radius,
            input.ageMs,input.serial,input.pressed,input.touched,input.accepted,lastVisualHeadErrorM_,
            (input.receivedPressed&kSideGripMask)!=0,input.receivedPressed);
    }
    gripWasDown_=input.pressed;
    // Arm a fresh trigger press only. Side grip keeps its existing binding.
    ArmLeftGrab(freeHand&&(hold.active||(nearHead&&!input.down)));
    if (wasHeld!=hold.active&&grabSamples_<32) {
        ++grabSamples_;
        const char* reason=diagnostic.reason==OffhandGrabReason::kHandUnavailable&&blocked?blocked:
            diagnostic.reason==OffhandGrabReason::kGripReleased?(!input.accepted?"input-withdrawn":"trigger-released"):
            offhandGrabReasonName(diagnostic.reason);
        const auto native=NativePhysicsBackend::GetSingleton().Snapshot();
        SKSE::log::info("CMS offhand head grip: {} reason={} heldMs={} button=left-trigger physical-left=true right-weapon=true inputFresh={} inputDown={} captured={} inputAgeMs={} inputSerial={} pressed={} touched={} accepted={} distanceM={} palmStepM={} chainExcessM={} targetErrorM={} maxChainExcessM={} maxTargetErrorM={} visualErrorM={} nativeLagM={} sideGripPressed={} receivedPressed=0x{:X}",
            hold.active?"held":"released",reason,heldMs,input.fresh,input.down,input.captured,
            input.ageMs,input.serial,input.pressed,input.touched,input.accepted,
            hand?length(palm.translation-head.centerM):-1.f,diagnostic.palmStepM,
            diagnostic.chainExcessM,diagnostic.targetErrorM,gripMaxChainExcessM_,
            gripMaxTargetErrorM_,lastVisualHeadErrorM_,native.ready?length(native.centerM-head.centerM):-1.f,
            (input.receivedPressed&kSideGripMask)!=0,input.receivedPressed);
    }
    constexpr std::int64_t progressMs[]={500,2000,5000,10000};
    if (hold.active&&gripProgressSamples_<std::size(progressMs)&&
        heldMs>=progressMs[gripProgressSamples_]) {
        ++gripProgressSamples_;
        SKSE::log::info("CMS offhand hold progress: heldMs={} button=left-trigger inputAgeMs={} inputSerial={} maxChainExcessM={} maxTargetErrorM={} visualErrorM={}",
            heldMs,input.ageMs,input.serial,gripMaxChainExcessM_,gripMaxTargetErrorM_,lastVisualHeadErrorM_);
    }
    return hold;
}
} // namespace cms::skyrimvr
