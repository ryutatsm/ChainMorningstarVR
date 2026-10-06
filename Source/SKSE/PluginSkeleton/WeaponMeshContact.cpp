#include "WeaponMeshContact.hpp"

#include "NativeContactRouter.hpp"
#include "../WeaponMeshContactCore.hpp"
#include <algorithm>
#include <cstring>
#include <vector>

namespace cms::skyrimvr {
namespace {
using namespace weaponmesh;
constexpr std::size_t kMaximumVertices=32768;
constexpr std::size_t kMaximumTriangles=32768;
constexpr std::size_t kMaximumTriangleQueries=180000;
constexpr float kEpisodeReleaseSeconds=.15f;

struct MeshSample {
    RE::NiPointer<RE::BSTriShape> geometry;
    RigidTransform transform;
    std::vector<Vec3> vertices;
    std::vector<std::array<std::uint16_t,3>> indices;
    std::uint64_t signature{};
    float radius{};
};
struct WeaponSample {
    RE::ActorHandle actor;
    RE::FormID base{};
    std::uintptr_t instance{};
    EquipmentContactPart part{EquipmentContactPart::kUnknown};
    std::vector<MeshSample> meshes;
    bool allReadable{true};
};
std::vector<WeaponSample> g_previous;
NativeHeadSnapshot g_previousHead;
std::uint64_t g_nextEpisode{};
struct EpisodeState {
    RE::ActorHandle actor;
    RE::FormID base{};
    std::uintptr_t instance{};
    EquipmentContactPart part{EquipmentContactPart::kUnknown};
    bool active{};
    float separatedSeconds{};
    bool observedThisFrame{};
};
// Episode memory is separate from readable geometry. Temporary GPU-only data,
// a missed frame or an unsupported mesh must never grant a second random roll.
std::vector<EpisodeState> g_episodes;
EpisodeState* EpisodeFor(const WeaponSample& sample) {
    auto it=std::find_if(g_episodes.begin(),g_episodes.end(),[&](const EpisodeState& e) {
        return e.actor==sample.actor&&e.base==sample.base&&e.instance==sample.instance&&e.part==sample.part;
    });
    if (it!=g_episodes.end()) return &*it;
    if (g_episodes.size()>=256) return nullptr;
    g_episodes.push_back({sample.actor,sample.base,sample.instance,sample.part});
    return &g_episodes.back();
}

RigidTransform Transform(const RE::NiTransform& t) {
    RigidTransform r{};
    r.translation={t.translate.x*kMetersPerSkyrimUnit,t.translate.y*kMetersPerSkyrimUnit,t.translate.z*kMetersPerSkyrimUnit};
    r.scale=t.scale;
    for (int i=0;i<3;++i) for (int j=0;j<3;++j) r.rotation.m[i][j]=t.rotate.entry[i][j];
    return r;
}
RigidTransform HeadTransform(const NativeHeadSnapshot& h) { return {h.centerM,h.rotation,h.shapeScale}; }

std::uint64_t Hash(std::uint64_t h,const void* bytes,std::size_t length) {
    const auto* p=static_cast<const unsigned char*>(bytes);
    for (std::size_t i=0;i<length;++i) { h^=p[i]; h*=1099511628211ULL; }
    return h;
}

// Static, unskinned full-precision BSTriShape layout is exposed by CommonLib.
// We never map the GPU buffer or assume that its absent CPU copy is readable.
bool ReadMesh(RE::BSTriShape* shape, MeshSample& out) {
    if (!shape || shape->AsDynamicTriShape()) return false;
    const auto& data=shape->GetGeometryRuntimeData();
    const auto& counts=shape->GetTrishapeRuntimeData();
    auto* render=data.rendererData;
    if (data.skinInstance || !render || !render->rawVertexData || !render->rawIndexData ||
        !counts.vertexCount || !counts.triangleCount || counts.vertexCount>kMaximumVertices ||
        counts.triangleCount>kMaximumTriangles) return false;
    auto desc=render->vertexDesc;
    using Flags=RE::BSGraphics::Vertex;
    if (!desc.HasFlag(Flags::VF_VERTEX) || !desc.HasFlag(Flags::VF_FULLPREC) ||
        desc.HasFlag(Flags::VF_SKINNED) || desc.GetFlags()!=data.vertexDesc.GetFlags()) return false;
    // A static full-precision position is the first float4 in the descriptor.
    // Require the encoded stride to equal CommonLib's public size computation;
    // reject unusual packing rather than read another attribute as a position.
    std::uint64_t encoded{};
    std::memcpy(&encoded,&desc,sizeof(encoded));
    const auto stride=static_cast<std::size_t>((encoded & 0xF)*4);
    if (stride<16 || stride>64 || stride!=desc.GetSize()) return false;
    out.transform=Transform(shape->world);
    if (!valid(out.transform)) return false;
    out.geometry.reset(shape);
    out.vertices.reserve(counts.vertexCount);
    out.indices.reserve(counts.triangleCount);
    std::uint64_t hash=1469598103934665603ULL;
    for (std::size_t i=0;i<counts.vertexCount;++i) {
        float p[3]{};
        std::memcpy(p,render->rawVertexData+i*stride,sizeof(p));
        const Vec3 v{p[0]*kMetersPerSkyrimUnit,p[1]*kMetersPerSkyrimUnit,p[2]*kMetersPerSkyrimUnit};
        if (!finite(v)||lengthSq(v)>10000.f) return false;
        out.vertices.push_back(v); out.radius=std::max(out.radius,length(v));
        hash=Hash(hash,p,sizeof(p));
    }
    for (std::size_t i=0;i<counts.triangleCount;++i) {
        std::array<std::uint16_t,3> tri{};
        std::memcpy(tri.data(),render->rawIndexData+i*3,sizeof(tri));
        if (tri[0]>=counts.vertexCount||tri[1]>=counts.vertexCount||tri[2]>=counts.vertexCount) return false;
        out.indices.push_back(tri); hash=Hash(hash,tri.data(),sizeof(tri));
    }
    out.signature=hash;
    return true;
}

void CollectMeshes(RE::NiAVObject* root,WeaponSample& out,std::size_t& visited) {
    if (!root || ++visited>256) { out.allReadable=false; return; }
    if (root->GetFlags().all(RE::NiAVObject::Flag::kHidden)) return;
    if (auto* shape=root->AsTriShape()) {
        MeshSample mesh;
        if (ReadMesh(shape,mesh)) out.meshes.push_back(std::move(mesh));
        else out.allReadable=false;
    } else if (root->AsGeometry()) {
        out.allReadable=false;
    }
    if (auto* node=root->AsNode()) for (const auto& child:node->GetChildren()) {
        if (child) CollectMeshes(child.get(),out,visited);
    }
}

bool DescendsFrom(RE::NiAVObject* object,RE::NiAVObject* ancestor) {
    if (!ancestor) return false;
    for (int i=0;object && i<128;++i,object=object->parent) if (object==ancestor) return true;
    return false;
}

EquipmentContactPart ExactHand(RE::Actor& actor,RE::TESForm* item,RE::NiAVObject* clone) {
    const bool right=actor.GetEquippedObject(false)==item,left=actor.GetEquippedObject(true)==item;
    if (!right&&!left) return EquipmentContactPart::kUnknown;
    if (right!=left) return right ? EquipmentContactPart::kRightWeapon:EquipmentContactPart::kLeftWeapon;
    auto* root=actor.Get3D(false);
    if (!root) return EquipmentContactPart::kUnknown;
    const bool underRight=DescendsFrom(clone,root->GetObjectByName(RE::BSFixedString("NPC R Hand [RHnd]")));
    const bool underLeft=DescendsFrom(clone,root->GetObjectByName(RE::BSFixedString("NPC L Hand [LHnd]")));
    if (underRight==underLeft) return EquipmentContactPart::kUnknown;
    return underRight ? EquipmentContactPart::kRightWeapon:EquipmentContactPart::kLeftWeapon;
}

std::vector<WeaponSample> CaptureNearby(const NativeHeadSnapshot& head) {
    std::vector<WeaponSample> result;
    auto* player=RE::PlayerCharacter::GetSingleton();
    auto* actors=RE::ProcessLists::GetSingleton();
    if (!player||!actors) return result;
    actors->ForEachHighActor([&](RE::Actor& actor) {
        if (&actor==player||actor.IsDead()||actor.IsPlayerTeammate()||!actor.IsHostileToActor(player)||
            actor.GetParentCell()!=player->GetParentCell()||!actor.Is3DLoaded()||!actor.IsWeaponDrawn()) return RE::BSContainer::ForEachResult::kContinue;
        const auto p=actor.GetPosition();
        // Candidate rejection only; this distance never certifies a contact.
        if (lengthSq(Vec3{p.x*kMetersPerSkyrimUnit,p.y*kMetersPerSkyrimUnit,p.z*kMetersPerSkyrimUnit}-head.centerM)>36.f) return RE::BSContainer::ForEachResult::kContinue;
        const auto& biped=actor.GetBiped(false);
        if (!biped) return RE::BSContainer::ForEachResult::kContinue;
        std::vector<RE::NiAVObject*> seen;
        for (std::size_t slot=32;slot<=40;++slot) {
            const auto& object=biped->objects[slot];
            auto* clone=object.partClone.get();
            if (!object.item||!object.item->IsWeapon()||!clone||std::find(seen.begin(),seen.end(),clone)!=seen.end()) continue;
            seen.push_back(clone);
            // Biped clone must belong to the current actor's live scene graph.
            if (!DescendsFrom(clone,actor.Get3D(false))) continue;
            const auto part=ExactHand(actor,object.item,clone);
            if (part==EquipmentContactPart::kUnknown) continue;
            const auto instance=ResolveWornEquipment(actor,part,object.item->GetFormID());
            if (!instance.baseForm||!instance.instance) continue;
            WeaponSample sample;
            sample.actor=actor.GetHandle(); sample.base=instance.baseForm;
            sample.instance=instance.instance; sample.part=part;
            std::size_t visited=0; CollectMeshes(clone,sample,visited);
            if (!sample.meshes.empty()) result.push_back(std::move(sample));
        }
        return RE::BSContainer::ForEachResult::kContinue;
    });
    return result;
}

bool SameWeapon(const WeaponSample& a,const WeaponSample& b) {
    return a.actor==b.actor && a.base==b.base && a.instance==b.instance && a.part==b.part;
}

struct QueryResult { bool complete{true}; bool hit{}; Vec3 pointM{}; };
QueryResult Query(const WeaponSample& previous,const WeaponSample& current,const RigidTransform& head0,
                  const RigidTransform& head1,std::size_t& budget) {
    QueryResult result;
    result.complete=previous.allReadable&&current.allReadable&&previous.meshes.size()==current.meshes.size();
    for (const auto& mesh:current.meshes) {
        auto it=std::find_if(previous.meshes.begin(),previous.meshes.end(),[&](const MeshSample& p) {
            return p.geometry.get()==mesh.geometry.get()&&p.signature==mesh.signature;
        });
        if (it==previous.meshes.end()) { result.complete=false; continue; }
        const int steps=sweepSteps(it->transform,mesh.transform,head0,head1,mesh.radius);
        if (!steps) { result.complete=false; continue; }
        for (int step=0;step<=steps;++step) {
            const float t=static_cast<float>(step)/static_cast<float>(steps);
            const auto w=interpolate(it->transform,mesh.transform,t),h=interpolate(head0,head1,t);
            // Broadphase only: entire geometry's actual vertex extent bounds.
            if (length(w.translation-h.translation)>mesh.radius*w.scale+.241f*h.scale) continue;
            std::vector<Vec3> local;
            local.reserve(mesh.vertices.size());
            for (const auto v:mesh.vertices) local.push_back(worldToLocalPoint(h,localToWorldPoint(w,v)));
            for (const auto tri:mesh.indices) {
                if (!budget) { result.complete=false; return result; }
                --budget;
                const auto hit=intersectHeadLocal(Triangle{{local[tri[0]],local[tri[1]],local[tri[2]]}});
                if (hit.hit) { result.hit=true; result.pointM=localToWorldPoint(h,hit.pointM); return result; }
            }
        }
    }
    return result;
}
} // namespace

WeaponMeshContact& WeaponMeshContact::GetSingleton() { static WeaponMeshContact instance; return instance; }

void WeaponMeshContact::Reset() { g_previous.clear(); g_previousHead={}; g_episodes.clear(); }

void WeaponMeshContact::Update(const NativeHeadSnapshot& head,float frameDeltaS,RE::FormID sourceWeapon) {
    if (!head.ready||!head.bodyIdentity||!head.generation||!sourceWeapon||!valid(HeadTransform(head))) { Reset(); return; }
    const bool validFrame=std::isfinite(frameDeltaS)&&frameDeltaS>0&&frameDeltaS<=.08f;
    if (g_previousHead.ready && head.physicsStep==g_previousHead.physicsStep) return;
    auto current=CaptureNearby(head);
    if (!g_previousHead.ready || g_previousHead.generation!=head.generation ||
        g_previousHead.bodyIdentity!=head.bodyIdentity || g_previousHead.leftHand!=head.leftHand ||
        head.physicsStep<g_previousHead.physicsStep) {
        g_previous=std::move(current); g_previousHead=head; g_episodes.clear(); return;
    }
    // Discontinuities establish a new motion baseline but preserve episode
    // memory, so a hitch cannot roll again for the same sustained contact.
    if (!validFrame) {
        for (auto& episode:g_episodes) episode.separatedSeconds=0;
        g_previous=std::move(current); g_previousHead=head; return;
    }
    for (auto& episode:g_episodes) episode.observedThisFrame=false;
    const auto previousHead=HeadTransform(g_previousHead),currentHead=HeadTransform(head);
    std::size_t budget=kMaximumTriangleQueries;
    for (auto& weapon:current) {
        const auto old=std::find_if(g_previous.begin(),g_previous.end(),[&](const WeaponSample& p) { return SameWeapon(p,weapon); });
        if (old==g_previous.end()) continue;
        auto* episode=EpisodeFor(weapon);
        if (!episode) continue;
        episode->observedThisFrame=true;
        const auto query=Query(*old,weapon,previousHead,currentHead,budget);
        if (!query.hit) {
            if (query.complete) episode->separatedSeconds+=frameDeltaS;
            else episode->separatedSeconds=0;
            if (episode->separatedSeconds>=kEpisodeReleaseSeconds) episode->active=false;
            continue;
        }
        episode->separatedSeconds=0;
        if (episode->active) continue;
        episode->active=true;
        ConfirmedEquipmentImpact request;
        request.target=weapon.actor; request.sourceWeapon=sourceWeapon;
        request.contactPosition={query.pointM.x*kSkyrimUnitsPerMeter,query.pointM.y*kSkyrimUnitsPerMeter,query.pointM.z*kSkyrimUnitsPerMeter};
        request.enemyAliveAtImpact=true;
        request.evidence.session=head.generation;
        request.evidence.contactSourceBody=head.bodyIdentity;
        request.evidence.sourceHand=head.leftHand?1:0;
        request.evidence.equippedBaseForm=weapon.base;
        request.evidence.equippedInstance=weapon.instance;
        request.evidence.part=weapon.part;
        request.evidence.verifiedIronBallContact=true;
        if (auto actor=weapon.actor.get()) request.evidence.targetActor=actor->GetFormID();
        const auto result=SubmitWeaponMeshImpact(request,++g_nextEpisode);
        (void)result;
    }
    for (auto& episode:g_episodes) if (!episode.observedThisFrame) episode.separatedSeconds=0;
    g_previous=std::move(current); g_previousHead=head;
}

} // namespace cms::skyrimvr
