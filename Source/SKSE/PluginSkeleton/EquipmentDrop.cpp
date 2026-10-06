#include "EquipmentDrop.hpp"

#include <SKSE/SKSE.h>
#include <cmath>
#include <random>

namespace cms::skyrimvr {
namespace {

constexpr auto kPluginName = "ChainMorningstarVR.esp";
constexpr RE::FormID kWeaponLocalID = 0x800;
EquipmentDropPolicy g_policy;

// Initialized only when a verified contact starts an actual game-thread
// equipment session. Merely loading this currently disconnected module does
// not access entropy or change inventory.
class LazyRandomGenerator {
public:
    using result_type = std::mt19937::result_type;
    static constexpr result_type min() { return std::mt19937::min(); }
    static constexpr result_type max() { return std::mt19937::max(); }
    result_type operator()()
    {
        static std::mt19937 generator{std::random_device{}()};
        return generator();
    }
};

bool IsHeadgear(RE::TESBoundObject* item)
{
    auto* armor = item ? item->As<RE::TESObjectARMO>() : nullptr;
    if (!armor) return false;
    using Slot = RE::BGSBipedObjectForm::BipedObjectSlot;
    return armor->HasPartOf(Slot::kHead) || armor->HasPartOf(Slot::kHair) ||
           armor->HasPartOf(Slot::kCirclet);
}

bool WornInRequestedSlot(RE::ExtraDataList* extra, EquipmentContactPart part)
{
    if (!extra) return false;
    if (part == EquipmentContactPart::kLeftWeapon) {
        return extra->HasType<RE::ExtraWornLeft>();
    }
    return extra->HasType<RE::ExtraWorn>();
}

} // namespace

void BeginEquipmentDropSession(std::uint64_t generation,
                               std::uintptr_t rightHeadBody,
                               std::uintptr_t leftHeadBody)
{
    g_policy.beginSession(generation, rightHeadBody, leftHeadBody);
}

EquipmentDropResult TryDropForConfirmedImpact(const ConfirmedEquipmentImpact& request)
{
    EquipmentDropResult result{};
    LazyRandomGenerator random;
    auto evidence = request.evidence;
    evidence.enemyOfPlayer = false;
    evidence.exactInstanceStillEquipped = false;
    evidence.droppable = false;

    auto* player = RE::PlayerCharacter::GetSingleton();
    auto target = request.target.get();
    auto* data = RE::TESDataHandler::GetSingleton();
    auto* cmsWeapon = data ? data->LookupForm<RE::TESObjectWEAP>(kWeaponLocalID, kPluginName) : nullptr;
    const bool finitePosition = std::isfinite(request.contactPosition.x) &&
        std::isfinite(request.contactPosition.y) && std::isfinite(request.contactPosition.z);
    // Never turn an unverified callback into evidence merely because the CMS
    // weapon is equipped. The caller's source-body proof is still required.
    if (!player || !target || target.get() == player || !cmsWeapon ||
        evidence.sourceHand > 1 || request.sourceWeapon != cmsWeapon->GetFormID() ||
        player->GetEquippedObject(evidence.sourceHand == 1) != cmsWeapon ||
        evidence.targetActor != target->GetFormID() || !finitePosition) {
        evidence.verifiedIronBallContact = false;
        result.decision = g_policy.evaluate(evidence, random);
        return result;
    }

    evidence.enemyOfPlayer = !target->IsDead() && !target->IsPlayerTeammate() &&
                            target->IsHostileToActor(player);
    if (!evidence.verifiedIronBallContact || !evidence.enemyOfPlayer) {
        result.decision = g_policy.evaluate(evidence, random);
        return result;
    }

    // GetInventory copies list containers but retains the actual ExtraDataList
    // pointers (CommonLib InventoryEntryData copy constructor). Resolve and use
    // the exact worn instance synchronously; no extra-list pointer is queued.
    auto inventory = target->GetInventory([&](RE::TESBoundObject& item) {
        return item.GetFormID() == evidence.equippedBaseForm;
    });
    RE::TESBoundObject* selectedItem = nullptr;
    RE::ExtraDataList* selectedExtra = nullptr;
    for (auto& [item, countedEntry] : inventory) {
        auto& [count, entry] = countedEntry;
        if (!item || count <= 0 || !entry || !entry->extraLists) continue;
        bool matchingPart = false;
        if (evidence.part == EquipmentContactPart::kHead) {
            matchingPart = IsHeadgear(item);
        } else if (evidence.part == EquipmentContactPart::kLeftWeapon ||
                   evidence.part == EquipmentContactPart::kRightWeapon) {
            const bool left = evidence.part == EquipmentContactPart::kLeftWeapon;
            matchingPart = item->IsWeapon() && target->GetEquippedObject(left) == item;
        }
        if (!matchingPart) continue;
        for (auto* extra : *entry->extraLists) {
            if (reinterpret_cast<std::uintptr_t>(extra) != evidence.equippedInstance ||
                !WornInRequestedSlot(extra, evidence.part)) continue;
            selectedItem = item;
            selectedExtra = extra;
            evidence.exactInstanceStillEquipped = true;
            evidence.droppable = item->GetPlayable() && !entry->IsQuestObject();
            break;
        }
        if (selectedExtra) break;
    }

    result.decision = g_policy.evaluate(evidence, random);
    if (result.decision != EquipmentDropDecision::kDrop) return result;

    // Actor::RemoveItem kDropping automatically handles equipped-item removal.
    // Do not unequip first: that can invalidate the exact worn-instance pointer.
    // Source precedent: HIGGS Hand::SpawnEquippedSelectedObject.
    result.droppedObject = target->RemoveItem(selectedItem, 1,
        RE::ITEM_REMOVE_REASON::kDropping, selectedExtra, nullptr,
        &request.contactPosition, nullptr);
    if (auto dropped = result.droppedObject.get()) {
        SKSE::log::info(
            "CMS equipment drop: actor={:08X}, item={:08X}, reference={:08X}, impact={}",
            evidence.targetActor, evidence.equippedBaseForm, dropped->GetFormID(), evidence.impactSerial);
    } else {
        // No retry on this impact: the engine may have removed inventory even
        // if its reference is not immediately available. Retrying could steal
        // another copy or alter a replacement item.
        SKSE::log::warn(
            "CMS equipment drop returned no reference: actor={:08X}, item={:08X}, impact={}; no retry",
            evidence.targetActor, evidence.equippedBaseForm, evidence.impactSerial);
    }
    return result;
}

} // namespace cms::skyrimvr
