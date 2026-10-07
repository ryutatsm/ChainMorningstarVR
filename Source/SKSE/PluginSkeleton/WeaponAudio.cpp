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
    UpdateLoop(air_,0x803,"air-cut",mix.air,head);
}
void WeaponAudio::EquipmentDropped(const RE::NiPoint3& position) {
    auto& sound=drops_[nextDrop_++%drops_.size()];Stop(sound);
    const bool accepted=Build(sound,0x804,position,.95f)&&sound.Play();
    SKSE::log::info("CMS equipment-drop audio: cue=disarm-strike accepted={}",accepted);
    if(!accepted) {Stop(sound);SKSE::log::warn("CMS equipment-drop sound unavailable; check matching ESP and sound files");}
}
void WeaponAudio::Reset() {
    Stop(scrape_.handle);Stop(air_.handle);scrape_={};air_={};
    for(auto& sound:drops_)Stop(sound);
    nextDrop_=0;
}
} // namespace cms::skyrimvr
