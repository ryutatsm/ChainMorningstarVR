#include "EquipmentDrop.hpp"
#include "VRFrameContext.hpp"
#include "WeaponAudio.hpp"

#include <SKSE/SKSE.h>
#include <cmath>
#include <random>

namespace cms::skyrimvr {
namespace {

constexpr auto kPluginName = "ChainMorningstarVR.esp";
constexpr RE::FormID kWeaponLocalID = 0x800;
EquipmentDropPolicy g_policy;

// Initialized only when a verified contact starts an actual game-thread
// equipment session. Merely loading the module does not access entropy or
// change inventory.
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

EquipmentItemKind ItemKind(RE::TESForm* item)
{
    if(!item) return EquipmentItemKind::kOther;
    if(item->IsWeapon()) return EquipmentItemKind::kWeapon;
    auto* armor=item->As<RE::TESObjectARMO>();
    if(!armor) return EquipmentItemKind::kOther;
    if(armor->HasPartOf(RE::BGSBipedObjectForm::BipedObjectSlot::kShield)) return EquipmentItemKind::kShield;
    return IsHeadgear(armor)?EquipmentItemKind::kHeadgear:EquipmentItemKind::kOther;
}

RE::TESForm* HeldItem(RE::Actor& actor,EquipmentContactPart part)
{
    if(!isHandEquipmentPart(part)||!actor.IsWeaponDrawn()) return nullptr;
    auto* item=actor.GetEquippedObject(part==EquipmentContactPart::kLeftHand);
    if(part==EquipmentContactPart::kLeftHand && !item)
        item=actor.GetWornArmor(RE::BGSBipedObjectForm::BipedObjectSlot::kShield);
    const auto kind=ItemKind(item);
    return kind==EquipmentItemKind::kWeapon ||
        (part==EquipmentContactPart::kLeftHand && kind==EquipmentItemKind::kShield)?item:nullptr;
}

bool WornInRequestedSlot(RE::ExtraDataList* extra,EquipmentContactPart part,RE::TESForm* item)
{
    return extra && wornFlagsMatch(part,ItemKind(item),extra->HasType<RE::ExtraWorn>(),extra->HasType<RE::ExtraWornLeft>());
}

} // namespace

bool IsHeldEquipmentType(RE::TESForm* item)
{
    const auto kind=ItemKind(item);
    return kind==EquipmentItemKind::kWeapon || kind==EquipmentItemKind::kShield;
}

EquipmentContactPart ResolveHandContactSlot(RE::Actor& actor,EquipmentContactPart part)
{
    auto* right=HeldItem(actor,EquipmentContactPart::kRightHand);
    auto* left=HeldItem(actor,EquipmentContactPart::kLeftHand);
    auto* weapon=right?right->As<RE::TESObjectWEAP>():nullptr;
    const bool both=weapon&&(weapon->IsTwoHandedSword()||weapon->IsTwoHandedAxe()||weapon->IsBow()||weapon->IsCrossbow());
    return handContactSlot(part,right?right->GetFormID():0,left?left->GetFormID():0,both);
}

EquipmentContactPart ResolveHeldItemSlot(RE::Actor& actor,RE::TESForm* item,RE::NiAVObject* clone)
{
    if(!IsHeldEquipmentType(item)||!actor.IsWeaponDrawn()) return EquipmentContactPart::kUnknown;
    auto* right=HeldItem(actor,EquipmentContactPart::kRightHand);
    auto* left=HeldItem(actor,EquipmentContactPart::kLeftHand);
    auto attachment=EquipmentContactPart::kUnknown;
    for(std::size_t depth=0;clone&&depth<128;++depth,clone=clone->parent) {
        const auto part=equipmentPartForBone(clone->name.c_str());
        if(isHandEquipmentPart(part)) {attachment=part;break;}
    }
    const auto shield=left&&ItemKind(left)==EquipmentItemKind::kShield?left->GetFormID():0;
    const bool shared=ResolveHandContactSlot(actor,EquipmentContactPart::kLeftHand)==EquipmentContactPart::kRightHand;
    const auto part=heldItemSlot(item->GetFormID(),right?right->GetFormID():0,left?left->GetFormID():0,shield,attachment,shared);
    return ResolveHandContactSlot(actor,part);
}

WornEquipmentInstance ResolveWornEquipment(RE::Actor& actor,
    EquipmentContactPart part, RE::FormID baseForm)
{
    if (part == EquipmentContactPart::kHead && baseForm == 0) {
        using Slot = RE::BGSBipedObjectForm::BipedObjectSlot;
        for (auto slot : {Slot::kHead, Slot::kHair, Slot::kCirclet}) {
            if (auto* armor = actor.GetWornArmor(slot)) {
                baseForm = armor->GetFormID();
                break;
            }
        }
    }
    if (isHandEquipmentPart(part)) {
        auto* equipped = HeldItem(actor,part);
        if(!baseForm && equipped) baseForm=equipped->GetFormID();
        if (!equipped || equipped->GetFormID() != baseForm) return {};
    } else if (part != EquipmentContactPart::kHead) {
        return {};
    }
    if (!baseForm) return {};
    WornEquipmentInstance result{};
    auto inventory = actor.GetInventory([&](RE::TESBoundObject& item) {
        return item.GetFormID() == baseForm;
    });
    for (auto& [item, countedEntry] : inventory) {
        auto& [count, entry] = countedEntry;
        if (!item || count <= 0 || !entry || !entry->extraLists ||
            (part == EquipmentContactPart::kHead && !IsHeadgear(item))) continue;
        for (auto* extra : *entry->extraLists) {
            if (!WornInRequestedSlot(extra, part, item)) continue;
            if (result.instance) return {}; // Cannot prove which duplicate was worn.
            result = {baseForm, reinterpret_cast<std::uintptr_t>(extra)};
        }
    }
    return result;
}

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
        player->GetEquippedObject(InventoryLeftHand(evidence.sourceHand == 1)) != cmsWeapon ||
        evidence.targetActor != target->GetFormID() || !finitePosition) {
        evidence.verifiedIronBallContact = false;
        result.decision = g_policy.evaluate(evidence, random);
        return result;
    }

    evidence.enemyOfPlayer = !target->IsPlayerTeammate() &&
        ((!target->IsDead() && target->IsHostileToActor(player)) ||
         (target->IsDead() && request.enemyAliveAtImpact));
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
        } else if (evidence.part == EquipmentContactPart::kLeftHand ||
                   evidence.part == EquipmentContactPart::kRightHand) {
            matchingPart = IsHeldEquipmentType(item) && HeldItem(*target,evidence.part) == item;
        }
        if (!matchingPart) continue;
        for (auto* extra : *entry->extraLists) {
            if (reinterpret_cast<std::uintptr_t>(extra) != evidence.equippedInstance ||
                !WornInRequestedSlot(extra, evidence.part, item)) continue;
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
        WeaponAudio::GetSingleton().EquipmentDropped(request.contactPosition);
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
