#include "OffhandInput.hpp"
#include <chrono>
#include <cstddef>
#include <limits>

namespace cms::skyrimvr {
namespace {
// Narrow ABI descriptions, checked against Odie/sksevr-mirror 7ed497e:
// PluginAPI.h SKSEVRInterface, GameVR.h/.cpp and openvr_1_0_12.h.
// Read the index-finger trigger before HIGGS's priority 66 callback.
struct VRInterface {
    std::uint32_t version,sourceVersion,targetVersion;
    bool (*actionsEnabled)();
    void (*registerController)(SKSE::PluginHandle,int,
        void(*)(std::uint32_t,ControllerState*,std::uint32_t,bool&));
};
static_assert(offsetof(VRInterface,registerController)==0x18);
OffhandTriggerInput capture;
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
    if (!input||size<sizeof(ControllerState)) return;
    capture.sample(index,*input,nowMs(),accepted);
}
void controllerFinal(std::uint32_t index,ControllerState* input,std::uint32_t size,bool&) {
    if (!input||size<sizeof(ControllerState)) return;
    capture.filterFinal(index,*input,nowMs());
}
}

void RegisterOffhandInput(const SKSE::LoadInterface* skse) {
    if (registered||!skse) return;
    auto* api=static_cast<VRInterface*>(skse->QueryInterface(0x10));
    if (!api||api->version<1||api->sourceVersion!=0x01000C00||!api->registerController) {
        SKSE::log::warn("CMS offhand trigger unavailable: SKSEVR controller interface mismatch");return;
    }
    api->registerController(skse->GetPluginHandle(),65,controller);
    api->registerController(skse->GetPluginHandle(),std::numeric_limits<int>::max(),controllerFinal);
    registered=true;
    SKSE::log::info("CMS offhand input registered: button=left-trigger mask=0x200000000 priority=65 final-filter=true side-grip=unchanged");
}
GripInput ReadLeftGrab() {
    if (!registered) return {};
    return capture.read(leftDevice(),nowMs());
}
void ArmLeftGrab(bool arm) {
    if (!registered) {capture.reset();return;}
    capture.arm(leftDevice(),arm,nowMs());
}
void ResetOffhandInput() {
    capture.reset();
}
} // namespace cms::skyrimvr
