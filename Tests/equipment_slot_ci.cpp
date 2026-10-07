#include "Source/SKSE/EquipmentSlotCore.hpp"
#include "Source/SKSE/ContactEpisodeCore.hpp"
#include <cassert>
#include <iostream>

int main() {
    using namespace cms;
    using Part=EquipmentContactPart;
    using Kind=EquipmentItemKind;
    constexpr auto head=Part::kHead,left=Part::kLeftHand,right=Part::kRightHand,none=Part::kUnknown;
    assert(equipmentPartForBone("NPC Head [Head]")==head);
    assert(equipmentPartForBone("NPC L Hand [LHnd]")==left);
    assert(equipmentPartForBone("NPC R Hand [RHnd]")==right);
    for(auto name:{"NPC Neck [Neck]","NPC L Forearm [LLar]","NPC R Forearm [RLar]",
                   "NPC Spine2 [Spn2]","NPC L Finger11 [LF11]","Gloves","Shield","Weapon",""})
        assert(equipmentPartForBone(name)==none);

    // Armor's ExtraWorn is correct for a left-hand shield, unlike a left sword.
    assert(wornFlagsMatch(left,Kind::kShield,true,false));
    assert(wornFlagsMatch(left,Kind::kShield,false,true));
    assert(!wornFlagsMatch(left,Kind::kShield,false,false));
    assert(!wornFlagsMatch(right,Kind::kShield,true,false));
    assert(!wornFlagsMatch(head,Kind::kShield,true,false));
    assert(wornFlagsMatch(head,Kind::kHeadgear,true,false));
    assert(!wornFlagsMatch(head,Kind::kHeadgear,false,true));
    assert(!wornFlagsMatch(left,Kind::kHeadgear,true,false));
    assert(!wornFlagsMatch(head,Kind::kWeapon,true,false));
    assert(!wornFlagsMatch(left,Kind::kOther,true,true)); // No gloves/spells.
    assert(wornFlagsMatch(left,Kind::kWeapon,false,true));
    assert(wornFlagsMatch(right,Kind::kWeapon,true,false));
    assert(!wornFlagsMatch(left,Kind::kWeapon,true,false));
    assert(!wornFlagsMatch(right,Kind::kWeapon,false,true));
    assert(!wornFlagsMatch(left,Kind::kWeapon,true,true));
    assert(!wornFlagsMatch(right,Kind::kWeapon,true,true)); // Ambiguous stacked copies.

    assert(heldItemSlot(1,1,2,0,none)==right);
    assert(heldItemSlot(2,1,2,0,none)==left);
    assert(heldItemSlot(3,1,3,3,none)==left); // Shield is armor, not a weapon slot.
    assert(heldItemSlot(3,1,0,0,none)==none); // Stowed/inventory item.
    assert(heldItemSlot(0,0,0,0,left)==none);
    // Identical dual-wield base forms need their actual scene attachment.
    assert(heldItemSlot(1,1,1,0,left)==left);
    assert(heldItemSlot(1,1,1,0,right)==right);
    assert(heldItemSlot(1,1,1,0,none)==none);
    assert(heldItemSlot(1,1,1,0,head)==none);
    assert(heldItemSlot(1,1,1,0,left,true)==right); // Shared two-handed inventory.
    assert(handContactSlot(left,1,0,true)==right);
    assert(handContactSlot(left,1,1,true)==right);
    assert(handContactSlot(left,1,2,true)==left);
    assert(handContactSlot(left,1,0,false)==left); // Empty other hand never disarms sword.
    assert(handContactSlot(left,0,0,true)==left);
    assert(handContactSlot(head,1,0,true)==head);
    assert(handContactSlot(none,1,0,true)==none);

    ContactEpisodeTracker episodes;
    const auto supportingHand=handContactSlot(left,1,0,true);
    assert(episodes.contact(0,10,100,supportingHand,1.0));
    assert(!episodes.contact(0,11,100,right,2.0)); // Same greatsword, no extra chance.
    assert(!episodes.mesh(0,100,right,1,3.0));
    assert(episodes.contact(0,12,100,head,3.0)); // A distinct head hit remains eligible.
    episodes.reset();
    assert(episodes.contact(0,10,100,left,1.0));
    assert(episodes.contact(0,11,100,right,1.0)); // Independent dual-wield equipment.
    std::cout << "PASS: head/hand equipment slots, shield worn flags, exact dual-wield and shared two-handed ownership\n";
}
