#pragma once
#include "EquipmentDropCore.hpp"
#include <string_view>

namespace cms {
// These are actual humanoid ragdoll nodes, never nearest-bone guesses. A
// forearm, neck, glove mesh or generic character controller is not a hand/head.
inline EquipmentContactPart equipmentPartForBone(std::string_view name) {
    if (name=="NPC Head [Head]") return EquipmentContactPart::kHead;
    if (name=="NPC L Hand [LHnd]") return EquipmentContactPart::kLeftHand;
    if (name=="NPC R Hand [RHnd]") return EquipmentContactPart::kRightHand;
    return EquipmentContactPart::kUnknown;
}
inline bool isHandEquipmentPart(EquipmentContactPart part) {
    return part==EquipmentContactPart::kLeftHand || part==EquipmentContactPart::kRightHand;
}
inline const char* equipmentPartName(EquipmentContactPart part) {
    switch(part) {
    case EquipmentContactPart::kHead: return "head";
    case EquipmentContactPart::kLeftHand: return "left-hand";
    case EquipmentContactPart::kRightHand: return "right-hand";
    default: return "unknown";
    }
}
enum class EquipmentItemKind { kOther, kHeadgear, kWeapon, kShield };
enum class EquipmentContactSurface { kUnknown, kHeadBody, kLeftHandBody, kRightHandBody, kItemBody, kItemMesh };
inline const char* equipmentSurfaceName(EquipmentContactSurface surface) {
    switch(surface) {
    case EquipmentContactSurface::kHeadBody:return "head-body";
    case EquipmentContactSurface::kLeftHandBody:return "left-hand-body";
    case EquipmentContactSurface::kRightHandBody:return "right-hand-body";
    case EquipmentContactSurface::kItemBody:return "held-item-body";
    case EquipmentContactSurface::kItemMesh:return "held-item-mesh";
    default:return "unknown";
    }
}

// Shields are armor and normally use ExtraWorn, even on the left arm. Weapons
// use distinct Worn/WornLeft lists; a list marked both ways is ambiguous.
inline bool wornFlagsMatch(EquipmentContactPart part,EquipmentItemKind kind,
                           bool worn,bool wornLeft) {
    if(part==EquipmentContactPart::kHead) return kind==EquipmentItemKind::kHeadgear && worn;
    if(kind==EquipmentItemKind::kShield) return part==EquipmentContactPart::kLeftHand && (worn||wornLeft);
    if(kind!=EquipmentItemKind::kWeapon) return false;
    if(part==EquipmentContactPart::kLeftHand) return wornLeft&&!worn;
    if(part==EquipmentContactPart::kRightHand) return worn&&!wornLeft;
    return false;
}

// Inventory ownership of a greatsword/bow is right-hand even when its left
// supporting hand is struck. Sharing that slot also shares ONE impact lottery.
inline EquipmentContactPart handContactSlot(EquipmentContactPart physicalPart,
    std::uint32_t rightForm,std::uint32_t leftForm,bool rightUsesBothHands) {
    if(physicalPart==EquipmentContactPart::kLeftHand && rightForm && rightUsesBothHands &&
        (!leftForm || leftForm==rightForm)) return EquipmentContactPart::kRightHand;
    return physicalPart;
}

inline EquipmentContactPart heldItemSlot(std::uint32_t item,std::uint32_t right,
    std::uint32_t left,std::uint32_t shield,EquipmentContactPart attachment,bool sharedTwoHanded=false) {
    if(!item) return EquipmentContactPart::kUnknown;
    if(item==shield) return EquipmentContactPart::kLeftHand;
    const bool r=item==right,l=item==left;
    if(r&&l) return sharedTwoHanded?EquipmentContactPart::kRightHand:
        (isHandEquipmentPart(attachment)?attachment:EquipmentContactPart::kUnknown);
    if(r) return EquipmentContactPart::kRightHand;
    if(l) return EquipmentContactPart::kLeftHand;
    return EquipmentContactPart::kUnknown;
}
} // namespace cms
