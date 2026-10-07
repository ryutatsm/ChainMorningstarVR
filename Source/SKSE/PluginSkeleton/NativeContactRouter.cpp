#include "NativeContactRouter.hpp"

#include "../ContactEpisodeCore.hpp"

#include <SKSE/SKSE.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <mutex>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace cms::skyrimvr {
namespace {

struct TargetSnapshot {
    RE::ActorHandle actor{};
    RE::FormID actorID{};
    std::uintptr_t root{};
    std::uintptr_t node{};
    std::uintptr_t body{};
    EquipmentContactPart part{};
    WornEquipmentInstance equipment{};
    bool enemyAlive{};
    EquipmentContactSurface surface{EquipmentContactSurface::kUnknown};
};

struct QueuedContact {
    TargetSnapshot target{};
    ConfirmedEquipmentImpact impact{};
};

struct RouterState {
    std::mutex mutex;
    std::uint64_t generation{};
    std::uintptr_t ownBody{};
    bool left{};
    float unitsPerHavokUnit{69.99125f};
    RE::FormID sourceWeapon{};
    std::uint64_t policyGeneration{};
    std::array<std::uint64_t, 2> serial{};
    ContactEpisodeTracker episodes{};
    std::unordered_map<std::uintptr_t, TargetSnapshot> targets;
    std::array<QueuedContact, 128> queue{};
    std::size_t queued{};
    std::size_t overflow{};
    std::uint64_t unmappedCallbacks{};
    std::uint64_t reportedUnmapped{};
    double nextSummary{};
};

RouterState g_state;

double ClockSeconds()
{
    return std::chrono::duration<double>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

std::uintptr_t BodyIdentity(RE::NiAVObject* node)
{
    auto* collision = node && node->collisionObject ?
        node->collisionObject->AsBhkNiCollisionObject() : nullptr;
    auto* rigid = collision && collision->body ? collision->body->AsBhkRigidBody() : nullptr;
    return rigid ? reinterpret_cast<std::uintptr_t>(rigid->referencedObject.get()) : 0;
}

RE::NiAVObject* FindNodeIdentity(RE::NiAVObject* root, std::uintptr_t identity)
{
    if (!root || !identity) return nullptr;
    std::vector<RE::NiAVObject*> pending{root};
    std::size_t budget = 8192;
    while (!pending.empty() && budget--) {
        auto* current = pending.back();
        pending.pop_back();
        if (reinterpret_cast<std::uintptr_t>(current) == identity) return current;
        if (auto* node = current->AsNode()) {
            for (auto& child : node->GetChildren()) if (child) pending.push_back(child.get());
        }
    }
    return nullptr;
}

std::unordered_map<std::uintptr_t, TargetSnapshot> CaptureTargets()
{
    std::unordered_map<std::uintptr_t, TargetSnapshot> result;
    std::unordered_set<std::uintptr_t> ambiguous;
    auto* player = RE::PlayerCharacter::GetSingleton();
    auto* processes = RE::ProcessLists::GetSingleton();
    if (!player || !processes) return result;
    const auto playerPosition = player->GetPosition();
    const auto add = [&](RE::NiAVObject* node, TargetSnapshot snapshot) {
        snapshot.body = BodyIdentity(node);
        if (!snapshot.body || ambiguous.contains(snapshot.body)) return;
        snapshot.node = reinterpret_cast<std::uintptr_t>(node);
        auto [where, inserted] = result.emplace(snapshot.body, snapshot);
        if (!inserted && (where->second.actorID != snapshot.actorID ||
                          where->second.part != snapshot.part ||
                          where->second.equipment.instance != snapshot.equipment.instance)) {
            result.erase(where);
            ambiguous.insert(snapshot.body);
        }
    };
    for (const auto& handle : processes->highActorHandles) {
        auto actor = handle.get();
        if (!actor || actor.get() == player) continue;
        auto* root = actor->Get3D();
        if (!root) continue;
        const auto position = actor->GetPosition();
        const float dx = position.x - playerPosition.x;
        const float dy = position.y - playerPosition.y;
        const float dz = position.z - playerPosition.z;
        // Only a read-budget cull. Contact is still proved by the real body pair.
        if (!std::isfinite(dx + dy + dz) || dx * dx + dy * dy + dz * dz > 650.0f * 650.0f) continue;
        TargetSnapshot snapshot{};
        snapshot.actor = handle;
        snapshot.actorID = actor->GetFormID();
        snapshot.root = reinterpret_cast<std::uintptr_t>(root);
        snapshot.enemyAlive = !actor->IsDead() && !actor->IsPlayerTeammate() &&
                              actor->IsHostileToActor(player);
        snapshot.part = EquipmentContactPart::kHead;
        snapshot.surface = EquipmentContactSurface::kHeadBody;
        snapshot.equipment = ResolveWornEquipment(*actor, snapshot.part);
        // Exact head only; never a neck or generic character controller.
        if (auto* head = root->GetObjectByName(RE::BSFixedString{"NPC Head [Head]"})) add(head, snapshot);

        if (!actor->IsWeaponDrawn()) continue;
        for (const auto* name : {"NPC L Hand [LHnd]", "NPC R Hand [RHnd]"}) {
            const auto physicalPart=equipmentPartForBone(name);
            snapshot.part=ResolveHandContactSlot(*actor,physicalPart);
            snapshot.surface=physicalPart==EquipmentContactPart::kLeftHand?
                EquipmentContactSurface::kLeftHandBody:EquipmentContactSurface::kRightHandBody;
            snapshot.equipment=ResolveWornEquipment(*actor,snapshot.part);
            if(auto* hand=root->GetObjectByName(RE::BSFixedString{name})) add(hand,snapshot);
        }

        const auto& biped = actor->GetBiped();
        if (!biped) continue;
        for (std::uint32_t slot = 0; slot < RE::BIPED_OBJECTS::kTotal; ++slot) {
            const auto& object = biped->objects[slot];
            if (!IsHeldEquipmentType(object.item) || !object.partClone) continue;
            if (!FindNodeIdentity(root,reinterpret_cast<std::uintptr_t>(object.partClone.get()))) continue;
            snapshot.part=ResolveHeldItemSlot(*actor,object.item,object.partClone.get());
            if (snapshot.part == EquipmentContactPart::kUnknown) continue;
            snapshot.surface=EquipmentContactSurface::kItemBody;
            snapshot.equipment = ResolveWornEquipment(*actor, snapshot.part, object.item->GetFormID());
            std::vector<RE::NiAVObject*> pending{object.partClone.get()};
            std::size_t budget = 2048;
            while (!pending.empty() && budget--) {
                auto* current = pending.back();
                pending.pop_back();
                // Weapon/shield surface contact and exact hand-body contact
                // are separate evidence paths, sharing one equipment slot.
                add(current, snapshot);
                if (auto* node = current->AsNode()) {
                    for (auto& child : node->GetChildren()) if (child) pending.push_back(child.get());
                }
            }
        }
    }
    return result;
}

bool MatchesSession(const RouterState& state, const ConfirmedEquipmentImpact& impact)
{
    return state.generation && impact.evidence.session == state.generation &&
        impact.evidence.sourceHand == static_cast<std::uint8_t>(state.left) &&
        impact.evidence.contactSourceBody == state.ownBody && state.ownBody;
}

void EnsurePolicySessionLocked(RouterState& state)
{
    if (state.policyGeneration == state.generation) return;
    BeginEquipmentDropSession(state.generation,
        state.left ? 0 : state.ownBody, state.left ? state.ownBody : 0);
    state.policyGeneration = state.generation;
    state.serial = {};
}

const char* DecisionName(EquipmentDropDecision decision)
{
    switch (decision) {
    case EquipmentDropDecision::kUnverifiedContact: return "unverified-contact";
    case EquipmentDropDecision::kWrongSession: return "wrong-session";
    case EquipmentDropDecision::kInvalidIdentity: return "invalid-identity";
    case EquipmentDropDecision::kDuplicateImpact: return "duplicate-episode";
    case EquipmentDropDecision::kNotEnemy: return "not-enemy";
    case EquipmentDropDecision::kNoEligibleEquipment: return "no-eligible-worn-instance";
    case EquipmentDropDecision::kKeptByChance: return "kept-by-one-third-draw";
    case EquipmentDropDecision::kDrop: return "drop";
    }
    return "unknown";
}

void LogDecision(const char* collector, const ConfirmedEquipmentImpact& impact,
                 const EquipmentDropResult& result)
{
    const auto& evidence = impact.evidence;
    if (evidence.impactSerial <= 24 || evidence.impactSerial % 128 == 0 ||
        result.decision == EquipmentDropDecision::kDrop || result.decision == EquipmentDropDecision::kKeptByChance) {
        SKSE::log::info(
            "CMS certified contact: collector={} generation={} episode={} sourceBody=0x{:X} actor={:08X} part={} slot={} surface={} item={:08X} wornInstance=0x{:X} outcome={}",
            collector, evidence.session, evidence.impactSerial, evidence.contactSourceBody,
            evidence.targetActor, static_cast<unsigned>(evidence.part), equipmentPartName(evidence.part),
            equipmentSurfaceName(impact.surface), evidence.equippedBaseForm,
            evidence.equippedInstance, DecisionName(result.decision));
    }
}

} // namespace

NativeContactRouter& NativeContactRouter::GetSingleton()
{
    static NativeContactRouter router;
    return router;
}

void NativeContactRouter::BeginSession(std::uint64_t generation,
    RE::hkpRigidBody* body, bool left, float unitsPerHavokUnit)
{
    if (!generation || !body || !std::isfinite(unitsPerHavokUnit) || unitsPerHavokUnit <= 0.0f) {
        EndSession();
        return;
    }
    std::scoped_lock lock(g_state.mutex);
    const auto identity = reinterpret_cast<std::uintptr_t>(body);
    if (g_state.generation == generation && g_state.ownBody == identity && g_state.left == left) return;
    g_state.generation = generation;
    g_state.ownBody = identity;
    g_state.left = left;
    g_state.unitsPerHavokUnit = unitsPerHavokUnit;
    g_state.policyGeneration = 0;
    g_state.episodes.reset();
    g_state.queued = 0;
    g_state.overflow = 0;
    g_state.unmappedCallbacks = 0;
    g_state.reportedUnmapped = 0;
    g_state.nextSummary = 0.0;
    g_state.targets.clear();
}

void NativeContactRouter::EndSession()
{
    std::scoped_lock lock(g_state.mutex);
    g_state.generation = 0;
    g_state.ownBody = 0;
    g_state.episodes.reset();
    g_state.queued = 0;
    g_state.targets.clear();
}

void NativeContactRouter::OnContactPoint(const RE::hkpContactPointEvent& event,
    RE::hkpRigidBody* ownedBody, bool left, std::uint64_t generation,
    std::uint64_t physicsStep)
{
    (void)physicsStep; // A frame number is never used as an impact serial.
    if (!ownedBody || !event.contactPoint) return;
    RE::hkpRigidBody* other = event.bodies[0] == ownedBody ? event.bodies[1] :
        (event.bodies[1] == ownedBody ? event.bodies[0] : nullptr);
    if (!other || other == ownedBody) return;
    alignas(16) float position[4];
    _mm_store_ps(position, event.contactPoint->position.quad);
    if (!std::isfinite(position[0]) || !std::isfinite(position[1]) || !std::isfinite(position[2])) return;
    std::scoped_lock lock(g_state.mutex);
    if (generation != g_state.generation || !generation || left != g_state.left ||
        reinterpret_cast<std::uintptr_t>(ownedBody) != g_state.ownBody) return;
    const auto found = g_state.targets.find(reinterpret_cast<std::uintptr_t>(other));
    if (found == g_state.targets.end()) { ++g_state.unmappedCallbacks; return; }
    const auto& target = found->second;
    if (!g_state.episodes.contact(static_cast<std::uint8_t>(left), target.body,
        target.actorID, target.part, ClockSeconds())) return;
    if (g_state.queued == g_state.queue.size()) { ++g_state.overflow; return; }
    auto& record = g_state.queue[g_state.queued++];
    record = {};
    record.target = target;
    record.impact.target = target.actor;
    record.impact.sourceWeapon = g_state.sourceWeapon;
    record.impact.contactPosition = {position[0] * g_state.unitsPerHavokUnit,
        position[1] * g_state.unitsPerHavokUnit, position[2] * g_state.unitsPerHavokUnit};
    record.impact.enemyAliveAtImpact = target.enemyAlive;
    record.impact.surface = target.surface;
    auto& evidence = record.impact.evidence;
    evidence.session = generation;
    evidence.contactSourceBody = g_state.ownBody;
    evidence.targetActor = target.actorID;
    evidence.equippedBaseForm = target.equipment.baseForm;
    evidence.equippedInstance = target.equipment.instance;
    evidence.part = target.part;
    evidence.sourceHand = static_cast<std::uint8_t>(left);
    evidence.verifiedIronBallContact = true;
}

void NativeContactRouter::OnCollisionRemoved(const RE::hkpCollisionEvent& event,
    RE::hkpRigidBody* ownedBody, bool left, std::uint64_t generation)
{
    RE::hkpRigidBody* other = event.bodies[0] == ownedBody ? event.bodies[1] :
        (event.bodies[1] == ownedBody ? event.bodies[0] : nullptr);
    std::scoped_lock lock(g_state.mutex);
    if (!other || generation != g_state.generation || left != g_state.left ||
        reinterpret_cast<std::uintptr_t>(ownedBody) != g_state.ownBody) return;
    g_state.episodes.removed(static_cast<std::uint8_t>(left),
        reinterpret_cast<std::uintptr_t>(other), ClockSeconds());
}

void NativeContactRouter::DrainAndRefresh()
{
    std::array<QueuedContact, 128> pending{};
    std::size_t count{};
    std::uint64_t generation{};
    {
        std::scoped_lock lock(g_state.mutex);
        EnsurePolicySessionLocked(g_state);
        if (!g_state.generation) return;
        generation = g_state.generation;
        count = g_state.queued;
        std::copy_n(g_state.queue.begin(), count, pending.begin());
        g_state.queued = 0;
        if (g_state.overflow) {
            SKSE::log::warn("CMS equipment contact queue saturated: {} episodes skipped", g_state.overflow);
            g_state.overflow = 0;
        }
        const auto now = ClockSeconds();
        if (now >= g_state.nextSummary && g_state.unmappedCallbacks != g_state.reportedUnmapped) {
            std::array<std::size_t,4> slots{};
            std::size_t equipped{};
            for(const auto& [body,target]:g_state.targets) {
                (void)body;
                const auto slot=static_cast<std::size_t>(target.part);
                if(slot<slots.size()) ++slots[slot];
                if(target.equipment.instance) ++equipped;
            }
            SKSE::log::info(
                "CMS contact mapping: generation={} certifiedTargetBodies={} headTargets={} leftHandTargets={} rightHandTargets={} eligibleWornTargets={} unmappedCallbacks={} (includes ground, scenery and non-equipment actor parts)",
                generation, g_state.targets.size(), slots[1], slots[2], slots[3], equipped, g_state.unmappedCallbacks);
            g_state.reportedUnmapped = g_state.unmappedCallbacks;
            g_state.nextSummary = now + 5.0;
        }
    }
    for (std::size_t i = 0; i < count; ++i) {
        auto& record = pending[i];
        auto actor = record.target.actor.get();
        if (!actor) continue;
        auto* root = actor->Get3D();
        if (reinterpret_cast<std::uintptr_t>(root) != record.target.root) continue;
        auto* node = FindNodeIdentity(root, record.target.node);
        if (!node || BodyIdentity(node) != record.target.body) continue;
        {
            std::scoped_lock lock(g_state.mutex);
            if (!MatchesSession(g_state, record.impact)) continue;
            record.impact.evidence.impactSerial = ++g_state.serial[record.impact.evidence.sourceHand];
        }
        const auto result = TryDropForConfirmedImpact(record.impact);
        LogDecision("havok-body", record.impact, result);
    }
    auto targets = CaptureTargets();
    auto* data = RE::TESDataHandler::GetSingleton();
    auto* weapon = data ? data->LookupForm<RE::TESObjectWEAP>(0x800, "ChainMorningstarVR.esp") : nullptr;
    std::scoped_lock lock(g_state.mutex);
    if (generation != g_state.generation) return;
    g_state.targets = std::move(targets);
    g_state.sourceWeapon = weapon ? weapon->GetFormID() : 0;
}

EquipmentDropResult SubmitWeaponMeshImpact(const ConfirmedEquipmentImpact& request,
    std::uint64_t meshEpisodeToken)
{
    auto impact = request;
    {
        std::scoped_lock lock(g_state.mutex);
        if (!MatchesSession(g_state, impact) || !impact.evidence.verifiedIronBallContact ||
            (impact.evidence.part != EquipmentContactPart::kLeftHand &&
             impact.evidence.part != EquipmentContactPart::kRightHand)) return {};
        EnsurePolicySessionLocked(g_state);
        if (!g_state.episodes.mesh(impact.evidence.sourceHand, impact.evidence.targetActor,
            impact.evidence.part, meshEpisodeToken, ClockSeconds())) {
            EquipmentDropResult duplicate{};
            duplicate.decision = EquipmentDropDecision::kDuplicateImpact;
            return duplicate;
        }
        impact.evidence.impactSerial = ++g_state.serial[impact.evidence.sourceHand];
    }
    const auto result = TryDropForConfirmedImpact(impact);
    LogDecision("weapon-mesh", impact, result);
    return result;
}

void EndWeaponMeshContact(std::uint64_t generation,std::uintptr_t sourceBody,
    std::uint8_t sourceHand,RE::FormID actor,EquipmentContactPart part,std::uint64_t token)
{
    std::scoped_lock lock(g_state.mutex);
    if(!generation || generation!=g_state.generation || sourceBody!=g_state.ownBody ||
        sourceHand!=static_cast<std::uint8_t>(g_state.left)) return;
    g_state.episodes.meshRemoved(sourceHand,actor,part,token,ClockSeconds());
}

} // namespace cms::skyrimvr
