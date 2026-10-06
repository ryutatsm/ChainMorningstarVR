# 0.6.0 physics test implementation boundary

The approved 0.5.3 meshes/materials are unchanged. This revision connects the
native head and equipment policy; it is not evidence of a passed in-game release.

HIGGS interface001 supplies its owned weapon rigid body. CMS clones only the
CMS_HeadNode fifteen-hull shape, validates centered uniform bounds and scaling,
retains the previous shape, and restores only a body still using our shape.
Prephysics pose updates use the API callback. No PlayerCharacter collisionNode
pointer replacement is used. Native calls are limited to Skyrim VR 1.4.15.0 and
are grounded in the pinned HIGGS/PLANCK sources, with notices in Source/ThirdParty.

Before moving the body, a native compound translation cast clips the target
against fixed world bodies. It uses the existing orientation; it does not prove
continuous angular contacts or generate equipment/damage events. Target-game
tests remain necessary for fast rotations and moving opponents.

Contacts return to the fixed-step solver through a bounded copied queue. The
solver applies penetration correction and velocity response once per physics
step. Scene loss, unequip, pause, load and teleport end the native ownership
session before old contacts can affect the next chain pose.

Equipment contact collection snapshots actor handles, actual collider identities
and exact worn-instance identities on the game thread. Physics callbacks enqueue
bounded identity records. Inventory is re-resolved on the game thread immediately
before Skyrim's actual-item drop path. A separate exact-convex/weapon-triangle
collector covers equipped NPC weapon meshes that lack a Havok body. It rejects
unreadable meshes and does not substitute hand proximity or broadphase overlap.

Completed-release gates remain in RELEASE_GATE_NEW_BUILD.md: target runtime
alignment, fast-contact reliability, native damage/block/perks/kill credit,
world-lock/lifetime behavior and extended gameplay have not been demonstrated.
Individual chain-link/world rigid bodies remain absent. Head reaction constrains
the connected simulated links but does not prove every link has world collision.
