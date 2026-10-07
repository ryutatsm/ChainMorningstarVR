// Contains an adapted NiCloningProcess ABI descriptor from adamhynek/HIGGS
// commit 93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee (GPL-3.0).
// See ../../ThirdParty/HIGGS/LICENSE. The remaining adapter is newly written.
#include "NativePhysicsBackend.hpp"
#include "NativeContactRouter.hpp"
#include "NativeWorldSweep.hpp"
#include "NativeChainCollision.hpp"
#include "PlanckBuildProbe.hpp"
#include "PlayerUpdateHook.hpp"
#include "VRFrameContext.hpp"
#include "../OffhandSelectionCore.hpp"
#include "../NativePoseCore.hpp"
#include "../../ThirdParty/HIGGS/HiggsInterface001.hpp"
#include <SKSE/SKSE.h>
#include <atomic>
#include <chrono>
#include <mutex>

namespace cms::skyrimvr {
namespace {
// Skyrim VR 1.4.15 addresses published in HIGGS 93bf67b's RE/offsets.cpp,
// plus removeContactListener in PLANCK f06fc95's RE/offsets.cpp. The plugin
// rejects every other executable version before these functions can run.
template<class T> T gameFunction(std::uintptr_t offset) {
    return reinterpret_cast<T>(REL::Module::get().base() + offset);
}
float havokUnitsPerMeter() {
    const float worldScale = *gameFunction<float*>(0x15B78F4);
    return worldScale * kSkyrimUnitsPerMeter;
}
Vec3 vector3(const RE::hkVector4& v) {
    alignas(16) float a[4]; _mm_store_ps(a, v.quad);
    return {a[0],a[1],a[2]};
}
float vectorW(const RE::hkVector4& v) {
    alignas(16) float a[4]; _mm_store_ps(a, v.quad); return a[3];
}
RE::hkVector4 hk(Vec3 v) { return {v.x,v.y,v.z,0}; }
RE::hkQuaternion quaternion(const Mat3& r) {
    float x{},y{},z{},w{};
    const float t=r.m[0][0]+r.m[1][1]+r.m[2][2];
    if(t>0) {const float s=std::sqrt(t+1)*2; w=.25f*s; x=(r.m[2][1]-r.m[1][2])/s; y=(r.m[0][2]-r.m[2][0])/s; z=(r.m[1][0]-r.m[0][1])/s;}
    else if(r.m[0][0]>r.m[1][1] && r.m[0][0]>r.m[2][2]) {const float s=std::sqrt(1+r.m[0][0]-r.m[1][1]-r.m[2][2])*2; w=(r.m[2][1]-r.m[1][2])/s; x=.25f*s; y=(r.m[0][1]+r.m[1][0])/s; z=(r.m[0][2]+r.m[2][0])/s;}
    else if(r.m[1][1]>r.m[2][2]) {const float s=std::sqrt(1+r.m[1][1]-r.m[0][0]-r.m[2][2])*2; w=(r.m[0][2]-r.m[2][0])/s; x=(r.m[0][1]+r.m[1][0])/s; y=.25f*s; z=(r.m[1][2]+r.m[2][1])/s;}
    else {const float s=std::sqrt(1+r.m[2][2]-r.m[0][0]-r.m[1][1])*2; w=(r.m[1][0]-r.m[0][1])/s; x=(r.m[0][2]+r.m[2][0])/s; y=(r.m[1][2]+r.m[2][1])/s; z=.25f*s;}
    RE::hkQuaternion out; out.vec=RE::hkVector4(x,y,z,w); return out;
}
Mat3 matrix(const RE::hkRotation& r) {
    Mat3 out{}; const Vec3 cols[]={vector3(r.col0),vector3(r.col1),vector3(r.col2)};
    for(int i=0;i<3;++i) {out.m[0][i]=cols[i].x;out.m[1][i]=cols[i].y;out.m[2][i]=cols[i].z;} return out;
}
RE::hkTransform identity() {
    RE::hkTransform t{}; t.rotation.col0=RE::hkVector4(1,0,0,0);t.rotation.col1=RE::hkVector4(0,1,0,0);t.rotation.col2=RE::hkVector4(0,0,1,0); return t;
}
// NiCloningProcess's scale is still unnamed in CommonLib 3.5.2. This exact
// descriptor and cleanup contract are from HIGGS include/RE/misc.h, under the
// bundled GPL-3.0 notice. No PlayerCharacter layout or collision node is edited.
struct VRCloneProcess {
    std::uint64_t words[12]{};
    std::uint8_t copyType{1}, nodeRelation{}, effectRelation{}, pad63{};
    char appendChar{'$'}; std::uint8_t padding[3]{};
    RE::NiPoint3 scale{1,1,1}; std::uint32_t pad74{};
    VRCloneProcess() {
        words[3]=REL::Module::get().base()+0x1E703BC;
        words[9]=REL::Module::get().base()+0x1E703B8;
    }
    ~VRCloneProcess() {
        using Cleanup=void(*)(std::uintptr_t);
        gameFunction<Cleanup>(0x1C8CA0)(reinterpret_cast<std::uintptr_t>(&words[7]));
        gameFunction<Cleanup>(0x1C8BE0)(reinterpret_cast<std::uintptr_t>(&words[1]));
    }
};
static_assert(sizeof(VRCloneProcess)==0x78);
static_assert(offsetof(VRCloneProcess,scale)==0x68);

struct State {
    std::mutex stateMutex, queueMutex;
    cms::higgs::IHiggsInterface001* api{};
    RE::NiPointer<RE::bhkShape> shape;
    RE::NiPointer<RE::bhkRigidBody> body;
    RE::NiPointer<RE::bhkRigidBody> expectedBody;
    RE::NiPointer<RE::bhkWorld> world;
    RE::hkRefPtr<RE::hkpShape> previousShape;
    std::int8_t previousQuality{};
    std::uint16_t previousDelay{};
    bool active{},left{}, poseValid{}, listenerAttached{};
    std::uint64_t generation{},step{};
    std::uint64_t chainSweeps{},chainContacts{};
    unsigned selectionGuardReports{};
    float unitScale{1},shapeScale{1}, frameDt{1.0f/90};
    HeadPose pose{};
    std::chrono::steady_clock::time_point submitted{};
    std::atomic<RE::hkpRigidBody*> contactBody{};
    std::atomic<std::uint64_t> contactGeneration{},contactStep{};
    std::atomic<bool> contactLeft{};
    std::atomic<float> contactUnits{1};
    std::vector<HeadWorldContact> contacts;
    NativeHeadSnapshot snapshot{};
    NativePoseContinuity continuity;
    unsigned poseRestoreReports{};
    std::uint64_t poseRestores{};
    std::atomic<RE::hkpRigidBody*> holdingHandBody{};
};
State& state() { static auto* s=new State; return *s; }
// CompareFilterInfo can run on physics workers too. They see an inactive TLS
// scope; no engine access, mutex or setting mutation occurs in this callback.
thread_local OffhandSelectionScope selectionScope;
cms::higgs::IHiggsInterface001::CollisionFilterComparisonResult selectionFilter(
    void*,std::uint32_t a,std::uint32_t b) {
    using Result=cms::higgs::IHiggsInterface001::CollisionFilterComparisonResult;
    return selectionScope.ignore(a,b)?Result::Ignore:Result::Continue;
}
RE::hkpRigidBody* havokBody(RE::bhkRigidBody* b) {
    return b ? static_cast<RE::hkpRigidBody*>(b->referencedObject.get()) : nullptr;
}
void refreshFilter(RE::hkpWorld* w, RE::hkpRigidBody* body) {
    using Fn=void(*)(RE::hkpWorld*,RE::hkpEntity*,std::int32_t,std::int32_t);
    gameFunction<Fn>(0xAB3110)(w,body,0,0); // FULL_CHECK / PROCESS_SHAPE_COLLECTIONS
}
Vec3 pointVelocity(RE::hkpRigidBody* b,Vec3 point) {
    return vector3(b->motion.linearVelocity)+cross(vector3(b->motion.angularVelocity),point-vector3(b->motion.motionState.sweptTransform.centerOfMass1));
}
class Listener final : public RE::hkpContactListener {
    void ContactPointCallback(const RE::hkpContactPointEvent& event) override {
        auto& s=state(); auto* own=s.contactBody.load();
        const auto generation=s.contactGeneration.load();
        if(!own||!event.contactPoint) return;
        const int index=event.bodies[0]==own?0:(event.bodies[1]==own?1:-1);
        if(index<0||!event.bodies[1-index]) return;
        // A ball grasp overlaps its holding fingers by design. The keyframed
        // hand must not become a solver plane that expels its own held ball.
        if(event.bodies[1-index]==s.holdingHandBody.load()) return;
        const float scale=s.contactUnits.load();
        if(!std::isfinite(scale)||scale<=0) return;
        const Vec3 point=vector3(event.contactPoint->position);
        const Vec3 normal=vector3(event.contactPoint->separatingNormal)*(index==0?1.0f:-1.0f);
        HeadWorldContact c{};
        c.physicsStep=s.contactStep.load();
        c.headCenterM=vector3(own->motion.motionState.transform.translation)/scale;
        c.normalWorld=normalized(normal);
        c.surfaceVelocityMps=pointVelocity(event.bodies[1-index],point)/scale;
        c.headVelocityMps=pointVelocity(own,point)/scale;
        c.pointM=point/scale;
        c.signedDistanceM=vectorW(event.contactPoint->separatingNormal)/scale;
        c.otherBodyIdentity=reinterpret_cast<std::uintptr_t>(event.bodies[1-index]);
        {std::lock_guard lock(s.queueMutex);if(s.contactBody.load()==own && s.contactGeneration.load()==generation && s.contacts.size()<128)s.contacts.push_back(c);}
        NativeContactRouter::GetSingleton().OnContactPoint(event,own,s.contactLeft.load(),generation,c.physicsStep);
    }
    void CollisionRemovedCallback(const RE::hkpCollisionEvent& event) override {
        auto& s=state();auto* own=s.contactBody.load();
        if(own&&(event.bodies[0]==own||event.bodies[1]==own))
            NativeContactRouter::GetSingleton().OnCollisionRemoved(event,own,s.contactLeft.load(),s.contactGeneration.load());
    }
};
Listener& listener() {static auto* p=new Listener;return *p;}

// stateMutex must be held. HIGGS may already have removed this body from its
// world; Ni/hk references keep it alive. Never restore a shape another mod owns.
void detach(State& s, bool alreadyWorldLocked=false) {
    selectionScope.end();
    s.contactBody.store(nullptr);
    s.contactGeneration.store(0);
    s.holdingHandBody.store(nullptr);
    s.continuity.reset();
    NativeContactRouter::GetSingleton().EndSession();
    auto cleanup=[&] {
        if(auto* b=havokBody(s.body.get())) {
            if(s.listenerAttached) {
                using Fn=void*(*)(RE::hkpEntity*,RE::hkpContactListener*);
                gameFunction<Fn>(0xAA7080)(b,&listener());
            }
            auto* ours=s.shape?static_cast<RE::hkpShape*>(s.shape->referencedObject.get()):nullptr;
            if(ours && b->collidable.shape==ours && s.previousShape) {
                b->collidable.broadPhaseHandle.objectQualityType=s.previousQuality;
                b->contactPointCallbackDelay=s.previousDelay;
                b->SetShape(s.previousShape.get());
                if(b->world)refreshFilter(b->world,b);
            }
        }
    };
    if(s.world && !alreadyWorldLocked){RE::BSWriteLockGuard lock(s.world->worldLock);cleanup();}else cleanup();
    s.listenerAttached=false;s.body.reset();s.world.reset();s.previousShape.reset();
    {std::lock_guard lock(s.queueMutex);s.contacts.clear();s.snapshot={};}
}

void prePhysics(void* worldPointer) {
    auto& s=state();std::lock_guard stateLock(s.stateMutex);
    if(!s.api||!s.active||!s.poseValid||!worldPointer) return;
    auto* wrapper=static_cast<RE::bhkWorld*>(worldPointer);
    auto* world=static_cast<RE::hkpWorld*>(wrapper->referencedObject.get());
    auto* object=s.api->GetWeaponRigidBody(s.left);
    auto* bodyWrapper=object?object->AsBhkRigidBody():nullptr;
    // The game thread certifies scene/equipment ownership immediately before
    // SubmitPose. A body newly created by HIGGS between that check and Havok
    // must wait for the next game-thread certification, never be adopted here.
    if(!bodyWrapper || bodyWrapper!=s.expectedBody.get()) {if(s.body)detach(s);return;}
    auto* body=havokBody(bodyWrapper);
    if(!body) {if(s.body)detach(s);return;}
    // Skyrim can step more than one physics world. An unrelated world callback
    // must not detach a still valid HIGGS body from the player's own world.
    if(!world||body->world!=world) return;
    if(body->motion.type!=RE::hkpMotion::MotionType::kKeyframed) {if(s.body)detach(s);return;}
    if(std::chrono::steady_clock::now()-s.submitted>std::chrono::milliseconds(200)) {
        if(s.body)detach(s);return;
    }
    if(s.body.get()!=bodyWrapper) {if(s.body)detach(s);}
    RE::BSWriteLockGuard worldLock(wrapper->worldLock);
    if(body->world!=world || s.api->GetWeaponRigidBody(s.left)!=bodyWrapper) return;
    // SetShape must execute synchronously; accepting a postponed operation
    // would allow a stale shape installation after the session is released.
    if(world->criticalOperationsLockCount!=0) return;
    auto* shape=static_cast<RE::hkpShape*>(s.shape->referencedObject.get());
    const RE::hkVector4 target=hk(s.pose.centerM*s.unitScale);
    const RE::hkQuaternion orientation=quaternion(s.pose.rotation);
    if(!s.body) {
        s.body.reset(bodyWrapper);s.world.reset(wrapper);
        s.previousShape.reset(const_cast<RE::hkpShape*>(body->collidable.shape));
        s.previousQuality=body->collidable.broadPhaseHandle.objectQualityType;
        s.previousDelay=body->contactPointCallbackDelay;
        if(!s.previousShape) {detach(s,true);return;}
        body->collidable.broadPhaseHandle.objectQualityType=9; // HK_COLLIDABLE_QUALITY_KEYFRAMED_REPORTING
        if(body->SetShape(shape)!=RE::hkWorldOperation::Result::kDone || body->collidable.shape!=shape) {
            body->collidable.broadPhaseHandle.objectQualityType=s.previousQuality;detach(s,true);return;
        }
        body->contactPointCallbackDelay=0;
        using SetPose=void(*)(RE::hkpEntity*,const RE::hkVector4&,const RE::hkQuaternion&);
        gameFunction<SetPose>(0xAA9030)(body,target,orientation);
        s.continuity.commit(s.pose.centerM,s.pose.rotation);
        body->motion.SetLinearVelocity(RE::hkVector4{});body->motion.SetAngularVelocity(RE::hkVector4{});
        using Add=void*(*)(RE::hkpEntity*,RE::hkpContactListener*);
        gameFunction<Add>(0xAA6FE0)(body,&listener());s.listenerAttached=true;
        refreshFilter(world,body);
        s.contactGeneration.store(s.generation);s.contactLeft.store(s.left);s.contactUnits.store(s.unitScale);s.contactBody.store(body);
        NativeContactRouter::GetSingleton().BeginSession(s.generation,body,s.left,kSkyrimUnitsPerMeter/s.unitScale);
        SKSE::log::info("Native head attached: generation={} body={:X} compound=15 scale={} havokUnitsPerMeter={}",s.generation,reinterpret_cast<std::uintptr_t>(body),s.shapeScale,s.unitScale);
    }
    if(body->collidable.shape!=shape){detach(s,true);s.active=false;SKSE::log::warn("Native head stopped: another owner replaced the shape");return;}
    const Vec3 incomingCenter=vector3(body->motion.motionState.transform.translation)/s.unitScale;
    const Mat3 incomingRotation=matrix(body->motion.motionState.transform.rotation);
    if(s.continuity.needsRestore(incomingCenter,incomingRotation)) {
        using SetPose=void(*)(RE::hkpEntity*,const RE::hkVector4&,const RE::hkQuaternion&);
        gameFunction<SetPose>(0xAA9030)(body,hk(s.continuity.center()*s.unitScale),quaternion(s.continuity.rotation()));
        ++s.poseRestores;
        if(s.poseRestoreReports<4 || s.poseRestores%500==0) {
            ++s.poseRestoreReports;
            SKSE::log::info("CMS native pose restored before sweep: displacementM={} total={} held={}",
                length(incomingCenter-s.continuity.center()),s.poseRestores,s.pose.held);
        }
    }
    auto* holdingHand=s.pose.held&&!s.left?s.api->GetHandRigidBody(true):nullptr;
    s.holdingHandBody.store(havokBody(holdingHand?holdingHand->AsBhkRigidBody():nullptr));
    ++s.step;s.contactStep.store(s.step);
    // This HIGGS callback runs immediately before hkpWorld::stepDeltaTime.
    // Its own PrePhysicsStep is empty in the pinned source. SimulatePlayerSpace's
    // hand-relative write has already occurred. It may also warp the body;
    // restore our previous endpoint above before querying the next path.
    float dt=world->dynamicsStepInfo.stepInfo.deltaTime;
    if(!std::isfinite(dt)||dt<1.0f/300||dt>.05f)dt=s.frameDt;
    const auto sweep=SweepNativeHeadAgainstStaticWorld(world,body,target,s.unitScale,s.step);
    if(s.step%500==0) {
        const auto current=matrix(body->motion.motionState.transform.rotation);
        const float cosine=std::clamp((dot(column(current,0),column(s.pose.rotation,0))+
            dot(column(current,1),column(s.pose.rotation,1))+
            dot(column(current,2),column(s.pose.rotation,2))-1.0f)*.5f,-1.0f,1.0f);
        SKSE::log::info("CMS head stability: step={} held={} targetStepM={} rotationStepRad={} sweepRecoveryM={} poseRestores={}",
            s.step,s.pose.held,length(s.pose.centerM-vector3(body->motion.motionState.transform.translation)/s.unitScale),
            std::acos(cosine),length(vector3(sweep.safeTargetHavok)-vector3(target))/s.unitScale,s.poseRestores);
    }
    if(sweep.hit) {
        auto contact=sweep.contact;
        // HIGGS overwrote the body's keyframe velocity earlier in this frame.
        // Measure the motion our head was about to make, not that hand target.
        contact.headVelocityMps=(vector3(target)-vector3(body->motion.motionState.transform.translation))/(s.unitScale*dt);
        std::lock_guard lock(s.queueMutex);if(s.contacts.size()<128)s.contacts.push_back(contact);
    }
    using Keyframe=void(*)(const RE::hkVector4&,const RE::hkQuaternion&,float,RE::hkpRigidBody*);
    gameFunction<Keyframe>(0xAF6DD0)(sweep.safeTargetHavok,orientation,1.0f/dt,body);
    s.continuity.commit(vector3(sweep.safeTargetHavok)/s.unitScale,s.pose.rotation);
    NativeHeadSnapshot snap{};
    snap.centerM=vector3(body->motion.motionState.transform.translation)/s.unitScale;
    snap.rotation=matrix(body->motion.motionState.transform.rotation);
    snap.velocityMps=vector3(body->motion.linearVelocity)/s.unitScale;snap.shapeScale=s.shapeScale;
    snap.bodyIdentity=reinterpret_cast<std::uintptr_t>(body);snap.generation=s.generation;snap.physicsStep=s.step;snap.leftHand=s.left;snap.ready=true;
    {std::lock_guard lock(s.queueMutex);s.snapshot=snap;}
}
} // namespace

NativePhysicsBackend& NativePhysicsBackend::GetSingleton(){static NativePhysicsBackend b;return b;}
bool NativePhysicsBackend::Initialize() {
    auto& s=state();std::lock_guard lock(s.stateMutex);if(s.api)return true;
    if(!REL::Module::IsVR()||REL::Module::get().version()!=REL::Version{1,4,15,0})return false;
    if(!GetDetectedPlanckBuildNumber()) {
        SKSE::log::warn("Native physics unavailable: PLANCK API missing; CMS simulation will not start");return false;
    }
    struct Message {void*(*getAPI)(unsigned int){};} message;
    auto* messaging=SKSE::GetMessagingInterface();
    if(!messaging || !messaging->Dispatch(0xF9279A57,&message,sizeof(void*),"HIGGS") || !message.getAPI) {
        SKSE::log::warn("Native physics unavailable: HIGGS interface001 missing");return false;
    }
    auto* api=static_cast<cms::higgs::IHiggsInterface001*>(message.getAPI(1));
    if(!api||api->GetBuildNumber()<1060000){SKSE::log::warn("Native physics requires HIGGS 1.6.0 or newer");return false;}
    s.api=api;s.api->AddPrePhysicsStepCallback(prePhysics);
    s.api->AddCollisionFilterComparisonCallback(selectionFilter);
    RegisterHiggsFrameUpdate(*api);
    SKSE::log::info("Native physics HIGGS API registered; build={}",api->GetBuildNumber());return true;
}
bool NativePhysicsBackend::BeginSession(RE::NiAVObject* node,bool left,std::uint64_t generation) {
    EndSession();auto& s=state();std::lock_guard lock(s.stateMutex);
    if(!s.api||!node||!generation)return false;
    if(!node->collisionObject) {SKSE::log::warn("Native head unavailable: equipped CMS_ROOT has no root collision; verify matching NIF deployment");return false;}
    auto* collision=node->collisionObject->AsBhkNiCollisionObject();
    auto* sourceBody=collision&&collision->body?collision->body->AsBhkRigidBody():nullptr;
    auto* native=havokBody(sourceBody);auto* source=native?native->collidable.shape:nullptr;
    if(!source||!source->userData||source->type!=RE::hkpShapeType::kList) {SKSE::log::warn("Native head unavailable: CMS_ROOT has no list collision shape");return false;}
    const auto* list=static_cast<const RE::hkpListShape*>(source);
    if(list->childInfo.size()!=15 || list->numDisabledChildren!=0)return false;
    for(const auto& child:list->childInfo)if(!child.shape||child.shape->type!=RE::hkpShapeType::kConvexVertices)return false;
    const float unitScale=havokUnitsPerMeter(),visualScale=node->world.scale;
    if(!std::isfinite(unitScale)||unitScale<.05f||unitScale>20||!std::isfinite(visualScale)||visualScale<.25f||visualScale>4)return false;
    RE::hkAabb bounds{};source->GetAabbImpl(identity(),0,bounds);
    const Vec3 low=vector3(bounds.min),high=vector3(bounds.max),extent=(high-low)*.5f;
    if(!isFinite(low)||!isFinite(high)||extent.x<=0||extent.y<=0||extent.z<=0)return false;
    // Bounds independently generated from the checked NIF's hull vertices +
    // convex radii. Require one uniform scale on all axes and a centered shape.
    const Vec3 expected = Vec3{.22373109f,.163f,.22373109f} * kModelScale;
    const float sx=extent.x/expected.x,sy=extent.y/expected.y,sz=extent.z/expected.z;
    if(!std::isfinite(sx)||sx<.001f||sx>1000||std::fabs(sx-sy)>.02f*sx||std::fabs(sx-sz)>.02f*sx||length(high+low)>.002f*sx) {
        SKSE::log::warn("Native head shape rejected: mismatching hull bounds {} {} {}",extent.x,extent.y,extent.z);return false;
    }
    VRCloneProcess clone;const float scale=unitScale*visualScale/sx;clone.scale={scale,scale,scale};
    using Clone=RE::NiObject*(*)(RE::NiObject*,void*);
    auto* copied=gameFunction<Clone>(0xC978E0)(source->userData,&clone);
    auto* cloned=static_cast<RE::bhkShape*>(copied);
    if(!cloned)return false;
    s.shape.reset(cloned);
    auto* clonedShape=static_cast<RE::hkpShape*>(cloned->referencedObject.get());
    if(!clonedShape||clonedShape==source||clonedShape->type!=RE::hkpShapeType::kList){s.shape.reset();return false;}
    clonedShape->GetAabbImpl(identity(),0,bounds);
    const Vec3 actual=(vector3(bounds.max)-vector3(bounds.min))*.5f;
    const Vec3 desired=expected*(unitScale*visualScale);
    if(!isFinite(actual)||length(actual-desired)>.012f*length(desired)){s.shape.reset();SKSE::log::warn("Native head clone scale failed validation");return false;}
    s.unitScale=unitScale;s.shapeScale=visualScale;s.left=left;s.generation=generation;s.step=0;s.active=true;
    s.chainSweeps=0;s.chainContacts=0;s.poseRestores=0;s.poseRestoreReports=0;
    SKSE::log::info("Native head prepared: fifteen convex hulls, sourceScale={} cloneScale={} visualScale={}",sx,scale,visualScale);return true;
}
void NativePhysicsBackend::EndSession() {
    auto& s=state();std::lock_guard lock(s.stateMutex);s.active=false;s.poseValid=false;detach(s);s.shape.reset();s.expectedBody.reset();s.selectionGuardReports=0;
}
void NativePhysicsBackend::SubmitPose(const HeadPose& pose,float dt) {
    auto& s=state();std::lock_guard lock(s.stateMutex);if(!s.active)return;
    if(!isFinite(pose.centerM)||!approximatelyOrthonormal(pose.rotation,.01f)||!std::isfinite(dt)||dt<=0)return;
    auto* object=s.api->GetWeaponRigidBody(s.left);
    s.expectedBody.reset(object?object->AsBhkRigidBody():nullptr);
    s.pose=pose;s.frameDt=std::clamp(dt,1.0f/300,.05f);s.poseValid=true;s.submitted=std::chrono::steady_clock::now();
}
std::vector<HeadWorldContact> NativePhysicsBackend::ConsumeContacts() {
    auto& s=state();std::lock_guard lock(s.queueMutex);std::vector<HeadWorldContact> result;result.swap(s.contacts);return result;
}
void NativePhysicsBackend::QueryChainContacts(const std::vector<ChainLinkSweep>& sweeps,
                                              std::vector<ChainLinkContact>& contacts) {
    auto& s=state();std::lock_guard stateLock(s.stateMutex);
    auto* body=havokBody(s.body.get());
    if(!s.active||!s.world||!s.shape||!body||s.contactBody.load()!=body||
       s.api->GetWeaponRigidBody(s.left)!=s.body.get())return;
    RE::BSReadLockGuard worldLock(s.world->worldLock);
    auto* world=static_cast<RE::hkpWorld*>(s.world->referencedObject.get());
    if(body->world!=world||body->collidable.shape!=s.shape->referencedObject.get())return;
    const auto before=contacts.size();
    QueryNativeChainCollisions(world,body,s.unitScale,sweeps,contacts);
    if(s.chainSweeps==0)
        SKSE::log::info("Chain collision queries active: links={} capsuleRadiusM={} capsuleHalfSegmentM={} damage=false response=chain-only",
            sweeps.size(),sweeps.empty()?0:sweeps.front().radiusM,sweeps.empty()?0:sweeps.front().halfSegmentM);
    s.chainSweeps+=sweeps.size();s.chainContacts+=contacts.size()-before;
}
NativeHeadSnapshot NativePhysicsBackend::Snapshot() const {
    auto& s=state();std::lock_guard stateLock(s.stateMutex);
    NativeHeadSnapshot result{};
    auto* body=havokBody(s.body.get());
    if(!s.active||!s.world||!body||s.contactBody.load()!=body||
       s.api->GetWeaponRigidBody(s.left)!=s.body.get())return result;
    // Hard keyframing updates velocity, not the current transform. Read after
    // the last completed physics step on the game thread, so weapon-mesh tests
    // never pair a cached pre-step head pose with current NPC geometry.
    RE::BSReadLockGuard worldLock(s.world->worldLock);
    if(body->world!=s.world->referencedObject.get()||
       body->collidable.shape!=s.shape->referencedObject.get())return result;
    result.centerM=vector3(body->motion.motionState.transform.translation)/s.unitScale;
    result.rotation=matrix(body->motion.motionState.transform.rotation);
    result.velocityMps=vector3(body->motion.linearVelocity)/s.unitScale;
    result.shapeScale=s.shapeScale;result.bodyIdentity=reinterpret_cast<std::uintptr_t>(body);
    result.generation=s.generation;result.physicsStep=s.step;result.leftHand=s.left;result.ready=true;
    result.chainSweeps=s.chainSweeps;result.chainContacts=s.chainContacts;
    return result;
}
bool NativePhysicsBackend::Available() const {
    auto& s=state();std::lock_guard lock(s.stateMutex);return s.api!=nullptr;
}
const char* NativePhysicsBackend::LeftHandBlockReason() const {
    auto& s=state();std::lock_guard lock(s.stateMutex);
    if(!s.active||s.left||!s.api)return "right-weapon-backend-unavailable";
    if(s.api->IsDisabled(true))return "higgs-hand-disabled";
    if(s.api->IsHoldingObject(true))return "higgs-holding-object";
    if(s.api->IsTwoHanding())return "higgs-two-handing";
    // Our selection-query filter prevents CMS from becoming SelectedTwoHand.
    // Retain the public busy guard for pulling and pending foreign grabs.
    if(!s.api->CanGrabObject(true))return "higgs-not-grabbable";
    return nullptr;
}

void NativePhysicsBackend::BeginHiggsSelectionQueries() {
    selectionScope.end();
    auto& s=state();std::lock_guard lock(s.stateMutex);
    if(!s.active||s.left||!s.api||!s.world||!s.body||!s.shape)return;
    auto* ui=RE::UI::GetSingleton();
    auto* player=RE::PlayerCharacter::GetSingleton();
    auto* data=RE::TESDataHandler::GetSingleton();
    auto* weapon=data?data->LookupForm<RE::TESObjectWEAP>(0x800,"ChainMorningstarVR.esp"):nullptr;
    if(!ui||ui->GameIsPaused()||!player||!weapon||!player->IsWeaponDrawn()||
       player->GetEquippedObject(InventoryLeftHand(false))!=weapon||
       player->GetEquippedObject(InventoryLeftHand(true))||
       s.api->IsDisabled(true)||s.api->IsHoldingObject(true)||s.api->IsHoldingObject(false)||
       s.api->GetWeaponRigidBody(false)!=s.body.get()||
       std::chrono::steady_clock::now()-s.submitted>std::chrono::milliseconds(200))return;
    auto* body=havokBody(s.body.get());
    if(!body||s.contactBody.load()!=body)return;
    RE::BSReadLockGuard worldLock(s.world->worldLock);
    if(body->world!=s.world->referencedObject.get()||
       body->collidable.shape!=s.shape->referencedObject.get())return;
    selectionScope.begin(body->collidable.broadPhaseHandle.collisionFilterInfo);
}

void NativePhysicsBackend::EndHiggsSelectionQueries() {
    const auto rejected=selectionScope.end();
    if(!rejected)return;
    auto& s=state();std::lock_guard lock(s.stateMutex);
    if(s.active&&s.selectionGuardReports<3) {
        ++s.selectionGuardReports;
        SKSE::log::info("CMS offhand selection guard: rejectedPickPairs={} scope=HIGGS-update right-CMS=true physics-filter-unchanged=true",rejected);
    }
}
} // namespace cms::skyrimvr
