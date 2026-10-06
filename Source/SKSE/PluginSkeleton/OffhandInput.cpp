#include "OffhandInput.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>

namespace cms::skyrimvr {
namespace {
// Narrow ABI descriptions, checked against Odie/sksevr-mirror 7ed497e:
// PluginAPI.h SKSEVRInterface, GameVR.h/.cpp and openvr_1_0_12.h.
// The callback reads the original grip before HIGGS's priority 66 callback.
struct ControllerState {
    std::uint32_t packet{};
    std::uint64_t pressed{}, touched{};
    float axes[10]{};
};
static_assert(sizeof(ControllerState)==64 && offsetof(ControllerState,pressed)==8);
struct VRInterface {
    std::uint32_t version,sourceVersion,targetVersion;
    bool (*actionsEnabled)();
    void (*registerController)(SKSE::PluginHandle,int,
        void(*)(std::uint32_t,ControllerState*,std::uint32_t,bool&));
};
static_assert(offsetof(VRInterface,registerController)==0x18);
constexpr std::uint64_t gripMask=1ull<<2;
std::array<std::atomic<std::uint64_t>,64> samples{};
std::atomic<std::uint64_t> armState{};
bool registered{};
std::uint64_t nowMs() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
std::uint32_t leftDevice() {
    // GetTrackedDeviceHand(left=0) is BSVRInterface slot 0x0D in SKSEVR.
    // Read-only access, guarded by the plugin's Skyrim VR 1.4.15 version check.
    auto* object=*reinterpret_cast<void**>(REL::Module::get().base()+0x2FEB9B0);
    if (!object) return 0xFFFFFFFFu;
    using Fn=std::uint32_t(*)(void*,std::uint32_t);
    auto* vtable=*reinterpret_cast<std::uintptr_t**>(object);
    return reinterpret_cast<Fn>(vtable[0x0D])(object,0);
}
void controller(std::uint32_t index,ControllerState* input,std::uint32_t size,bool& accepted) {
    if (index>=samples.size()||!input||size<sizeof(ControllerState)) return;
    const auto now=nowMs(),old=samples[index].load(),arm=armState.load();
    const bool down=accepted&&(input->pressed&gripMask)!=0;
    const bool fresh=now-(old>>8)<150;
    const bool armed=(arm&255)==index+1&&now-(arm>>8)<150;
    // Once claimed, consume only this grip until release, even if stretch or
    // obstruction made CMS let go. Never leak a mid-press into HIGGS two-hand.
    const bool claimed=down&&((fresh&&(old&2)) || (armed&&!(old&1)));
    samples[index].store((now<<8)|(down?1:0)|(claimed?2:0));
    if (claimed) {input->pressed&=~gripMask;input->touched&=~gripMask;}
}
}

void RegisterOffhandInput(const SKSE::LoadInterface* skse) {
    if (registered||!skse) return;
    auto* api=static_cast<VRInterface*>(skse->QueryInterface(0x10));
    if (!api||api->version<1||api->sourceVersion!=0x01000C00||!api->registerController) {
        SKSE::log::warn("CMS offhand grip unavailable: SKSEVR controller interface mismatch");return;
    }
    api->registerController(skse->GetPluginHandle(),65,controller);
    registered=true;
    SKSE::log::info("CMS offhand grip input registered: physical left grip, priority=65");
}
GripInput ReadLeftGrip() {
    if (!registered) return {};
    const auto device=leftDevice();
    if (device>=samples.size()) return {};
    const auto value=samples[device].load();
    return {value!=0&&nowMs()-(value>>8)<150,(value&1)!=0,(value&2)!=0};
}
void ArmLeftGrip(bool arm) {
    if (!registered||!arm) {armState.store(0);return;}
    const auto device=leftDevice();
    armState.store(device<samples.size() ? (nowMs()<<8)|(device+1) : 0);
}
void ResetOffhandInput() {
    armState.store(0);
    for (auto& sample:samples) sample.fetch_and(~std::uint64_t{2});
}
} // namespace cms::skyrimvr
