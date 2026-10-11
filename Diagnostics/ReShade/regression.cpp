#include <cstdio>
#include <cstdint>
#include <stdexcept>
#include <iostream>

namespace vr { enum EVRInitError { None = 0, NotInitialized = 109 }; struct IVRCompositor { int dummy; }; }
static void* result = nullptr;
static int resolves = 0, installs = 0, slot = -1;
static void* Resolve(const char*, vr::EVRInitError* error) {
    ++resolves;
    if (error) *error = result ? vr::None : vr::NotInitialized;
    return result;
}
namespace reshade {
namespace hook { using address = std::uintptr_t; }
namespace hooks {
    template<class T> auto call(T) { return Resolve; }
    void install(const char*, void*, int index, hook::address) { ++installs; slot = index; }
}}
static void* vtable_from_instance(vr::IVRCompositor* p) {
    if (!p) throw std::runtime_error("null interface dereference");
    return p;
}
static void IVRCompositor_Submit_007() {}
static void IVRCompositor_Submit_008() {}
static void IVRCompositor_Submit_009() {}
static void IVRCompositor_Submit_012() {}
namespace original {
void* VR_GetGenericInterface(const char* pchInterfaceVersion, vr::EVRInitError* peError) {
#include "original.inc"
}}
namespace patched {
void* VR_GetGenericInterface(const char* pchInterfaceVersion, vr::EVRInitError* peError) {
#include "patched.inc"
}}
static void require(bool v) { if (!v) throw std::runtime_error("failed assertion"); }
static void reset(void* p) { result=p;resolves=0;installs=0;slot=-1; }
int main() {
    try {
        vr::EVRInitError error=vr::None;
        reset(nullptr); bool failed=false;
        try { original::VR_GetGenericInterface("IVRCompositor_022", &error); }
        catch (const std::runtime_error&) { failed=true; }
        require(failed && error==vr::NotInitialized && resolves==1);
        reset(nullptr);
        require(patched::VR_GetGenericInterface("IVRCompositor_022", &error)==nullptr);
        require(resolves==1 && installs==0 && error==vr::NotInitialized);
        std::cout << "PASS null compositor: original failure reproduced; patched preserves failure return and error\n";
        vr::IVRCompositor object{};
        for (const auto& c : {std::pair{"IVRCompositor_022",5}, {"IVRCompositor_009",4}, {"IVRCompositor_008",6}, {"IVRCompositor_007",6}}) {
            reset(&object);
            require(patched::VR_GetGenericInterface(c.first,&error)==&object);
            require(resolves==1 && installs==1 && slot==c.second && error==vr::None);
            std::cout << "PASS " << c.first << ": original instance and hook slot preserved\n";
        }
        for (const char* name : {"IVRCompositor_006", "IVRSystem_019"}) {
            reset(&object);
            require(patched::VR_GetGenericInterface(name,&error)==&object);
            require(resolves==1 && installs==0);
            std::cout << "PASS " << name << ": passthrough without hook\n";
        }
        reset(nullptr);
        require(patched::VR_GetGenericInterface("IVRSystem_019",nullptr)==nullptr);
        require(resolves==1 && installs==0);
        std::cout << "PASS null non-compositor and optional error pointer\n";
        std::cout << "8 regression cases passed; engine interfaces mocked; no replacement DLL built\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
