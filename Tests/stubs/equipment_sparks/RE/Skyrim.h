#pragma once
#include <cstdint>
#include <string>

namespace RE {
struct NiPoint3 { float x{}, y{}, z{}; };
struct NiAVObject {};
struct TESObjectCELL {
    bool attached{true};
    bool IsAttached() const { return attached; }
};
struct Actor {
    TESObjectCELL* cell{};
    NiAVObject* node{};
    TESObjectCELL* GetParentCell() { return cell; }
    NiAVObject* Get3D() { return node; }
};
struct BSTempEffectParticle {
    static inline unsigned calls{};
    static inline bool accept{true};
    static inline TESObjectCELL* spawnedCell{};
    static inline NiAVObject* target{};
    static inline NiPoint3 position{}, rotation{};
    static inline float lifetime{}, scale{};
    static inline std::uint32_t flags{};
    static inline std::string model;
    static BSTempEffectParticle* Spawn(TESObjectCELL* c, float life, const char* m,
        const NiPoint3& r, const NiPoint3& p, float s, std::uint32_t f, NiAVObject* t) {
        ++calls; spawnedCell=c; lifetime=life; model=m; rotation=r; position=p;
        scale=s; flags=f; target=t;
        static BSTempEffectParticle effect;
        return accept ? &effect : nullptr;
    }
};
}
