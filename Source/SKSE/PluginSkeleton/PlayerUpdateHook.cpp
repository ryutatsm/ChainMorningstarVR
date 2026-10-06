#include "PlayerUpdateHook.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>

#include "RuntimeService.hpp"

namespace cms::skyrimvr {
namespace {

struct PlayerUpdateHook {
    static void Thunk(RE::PlayerCharacter* self, float delta)
    {
        func(self, delta);
        if (!std::isfinite(delta)) return;
        const float safeDelta = std::clamp(delta, 0.0f, 0.100f);
        RuntimeService::GetSingleton().tick(safeDelta);
    }

    static inline REL::Relocation<decltype(Thunk)> func;
};

} // namespace

bool InstallPlayerUpdateHook()
{
    static bool installed = false;
    if (installed) return true;
    if (!REL::Module::IsVR()) {
        SKSE::log::critical("ChainMorningstarVR: refused PlayerUpdate hook outside Skyrim VR");
        return false;
    }

    constexpr std::size_t kActorUpdateVRVtableSlot = 0x0AF;
    REL::Relocation<std::uintptr_t> playerVtable{ RE::VTABLE_PlayerCharacter[0] };
    PlayerUpdateHook::func = playerVtable.write_vfunc(kActorUpdateVRVtableSlot, PlayerUpdateHook::Thunk);
    installed = true;
    SKSE::log::info("ChainMorningstarVR: installed PlayerCharacter::Update VR frame hook at vtable slot 0x{:X}",
                    kActorUpdateVRVtableSlot);
    return true;
}

} // namespace cms::skyrimvr
