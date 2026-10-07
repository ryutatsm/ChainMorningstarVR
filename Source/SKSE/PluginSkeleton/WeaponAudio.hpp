#pragma once
#include <RE/Skyrim.h>
#include <array>
#include <cstddef>
#include "../MotionAudioCore.hpp"

namespace cms::skyrimvr {
// Game-thread only. No audio is created from a Havok callback.
class WeaponAudio {
public:
    static WeaponAudio& GetSingleton();
    void Update(MotionAudioMix mix,RE::NiAVObject* head);
    void EquipmentDropped(const RE::NiPoint3& position);
    void Reset();
private:
    struct Loop { RE::BSSoundHandle handle{}; bool failed{}; unsigned samples{}; };
    void UpdateLoop(Loop& loop,RE::FormID localID,const char* name,float volume,RE::NiAVObject* head);
    Loop scrape_{},air_{};
    std::array<RE::BSSoundHandle,4> drops_{};
    std::size_t nextDrop_{};
};
} // namespace cms::skyrimvr
