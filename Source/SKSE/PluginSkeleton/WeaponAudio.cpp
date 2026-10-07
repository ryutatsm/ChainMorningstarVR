#include "WeaponAudio.hpp"
#include <SKSE/SKSE.h>
#include <algorithm>
#include <cmath>

namespace cms::skyrimvr {
namespace {
bool Build(RE::BSSoundHandle& handle,RE::FormID localID,const RE::NiPoint3& position,float volume) {
    auto* data=RE::TESDataHandler::GetSingleton();
    auto* audio=RE::BSAudioManager::GetSingleton();
    auto* descriptor=data?data->LookupForm<RE::BGSSoundDescriptorForm>(localID,"ChainMorningstarVR.esp"):nullptr;
    return descriptor && audio && audio->BuildSoundDataFromDescriptor(handle,descriptor,0x10) &&
        handle.soundID!=RE::BSSoundHandle::kInvalidID && handle.SetPosition(position) &&
        handle.SetVolume(volume);
}
void Stop(RE::BSSoundHandle& handle) {
    if(handle.soundID!=RE::BSSoundHandle::kInvalidID) handle.Stop();
    handle=RE::BSSoundHandle{};
}
}
WeaponAudio& WeaponAudio::GetSingleton() { static auto* instance=new WeaponAudio; return *instance; }

void WeaponAudio::UpdateLoop(Loop& loop,RE::FormID id,const char* name,float volume,RE::NiAVObject* head) {
    if(!head || !std::isfinite(volume) || volume<=0.0f) {
        if(loop.handle.soundID!=RE::BSSoundHandle::kInvalidID && loop.samples<8)
            SKSE::log::info("CMS motion audio: cue={} state=stop",name);
        Stop(loop.handle);return;
    }
    if(loop.failed) return;
    volume=std::clamp(volume,0.0f,1.0f);
    if(loop.handle.soundID==RE::BSSoundHandle::kInvalidID) {
        bool accepted=Build(loop.handle,id,head->world.translate,volume);
        if(accepted) {loop.handle.SetObjectToFollow(head);accepted=loop.handle.Play();}
        if(loop.samples++<8) SKSE::log::info("CMS motion audio: cue={} state=start accepted={} volume={:.3f}",name,accepted,volume);
        if(!accepted) {
            SKSE::log::warn("CMS motion audio unavailable: cue={} localDescriptor={:08X}; check matching ESP and sound files",name,id);
            Stop(loop.handle);loop.failed=true;
        }
    } else if(!loop.handle.SetVolume(volume)) {
        Stop(loop.handle);loop.failed=true;
        SKSE::log::warn("CMS motion audio volume update failed: cue={}",name);
    }
}
void WeaponAudio::Update(MotionAudioMix mix,RE::NiAVObject* head) {
    UpdateLoop(scrape_,0x802,"iron-scrape",mix.scrape,head);
    if(!head||mix.airStopped) {Stop(air_);return;}
    if(airFailed_||!std::isfinite(mix.air)||mix.air<=0) return;
    // Descriptor 803 is non-looping. A silent frame lets the short tail finish;
    // only a new swing request starts another sample. No per-frame restart.
    Stop(air_);
    const float volume=std::clamp(mix.air,0.0f,1.0f);
    bool accepted=Build(air_,0x803,head->world.translate,volume);
    if(accepted) {air_.SetObjectToFollow(head);accepted=air_.Play();}
    if(airSamples_++<24)
        SKSE::log::info("CMS motion audio: cue=air-cut state=start accepted={} volume={:.3f} mode=swing-one-shot",accepted,volume);
    if(!accepted) {
        Stop(air_);airFailed_=true;
        SKSE::log::warn("CMS swing sound unavailable: localDescriptor=00000803; check matching ESP and sound files");
    }
}
void WeaponAudio::EquipmentDropped(const RE::NiPoint3& position) {
    auto& sound=drops_[nextDrop_++%drops_.size()];Stop(sound);
    const bool accepted=Build(sound,0x804,position,.95f)&&sound.Play();
    SKSE::log::info("CMS equipment-drop audio: cue=disarm-strike accepted={}",accepted);
    if(!accepted) {Stop(sound);SKSE::log::warn("CMS equipment-drop sound unavailable; check matching ESP and sound files");}
}
void WeaponAudio::Reset() {
    Stop(scrape_.handle);Stop(air_);scrape_={};airFailed_=false;airSamples_=0;
    for(auto& sound:drops_)Stop(sound);
    nextDrop_=0;
}
} // namespace cms::skyrimvr
