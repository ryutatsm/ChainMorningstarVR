#include <SKSE/SKSE.h>

SKSEPluginLoad(const SKSE::LoadInterface* skse)
{
    SKSE::Init(skse);
    SKSE::log::info("ChainMorningstarVR v0.4.0 CI probe loaded");
    return true;
}
