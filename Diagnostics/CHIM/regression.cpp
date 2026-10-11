#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <utility>

struct NullReference : std::runtime_error {
    NullReference() : std::runtime_error("null reference reached a dereference") {}
};
static std::function<void()> onTypeQuery;
namespace RE {
enum class FormType { Misc, ActorCharacter = 62 };
template<class T> struct NiPointer {
    std::shared_ptr<T> value;
    NiPointer() = default;
    NiPointer(std::shared_ptr<T> p) : value(std::move(p)) {}
    explicit operator bool() const { return bool(value); }
    T* get() const { return value.get(); }
    T* operator->() const { if (!value) throw NullReference(); return value.get(); }
};
struct ObjectRefHandle;
struct TESObjectREFR : std::enable_shared_from_this<TESObjectREFR> {
    virtual ~TESObjectREFR() = default;
    FormType type = FormType::Misc;
    FormType GetFormType() { if (onTypeQuery) onTypeQuery(); return type; }
    template<class T> T* As() { return dynamic_cast<T*>(this); }
    const char* GetDisplayFullName() const { return "fixture"; }
    ObjectRefHandle GetHandle();
};
struct Actor : TESObjectREFR { Actor() { type = FormType::ActorCharacter; } };
struct HandleState {
    unsigned id = 0;
    unsigned resolves = 0;
    std::weak_ptr<TESObjectREFR> object;
};
struct ObjectRefHandle {
    std::shared_ptr<HandleState> state = std::make_shared<HandleState>();
    explicit operator bool() const { return state->id != 0; }
    NiPointer<TESObjectREFR> get() const { ++state->resolves; return state->object.lock(); }
};
inline ObjectRefHandle TESObjectREFR::GetHandle() {
    ObjectRefHandle handle;
    handle.state->id = 123;
    handle.state->object = shared_from_this();
    return handle;
}
struct CrosshairPickData {
    static inline CrosshairPickData* instance = nullptr;
    ObjectRefHandle target;
    static CrosshairPickData* GetSingleton() { return instance; }
    ObjectRefHandle GetActiveTarget() const { return target; }
};
struct PlayerCharacter {
    static inline PlayerCharacter* instance = nullptr;
    std::weak_ptr<TESObjectREFR> grabbed;
    unsigned grabs = 0;
    static PlayerCharacter* GetSingleton() { return instance; }
    NiPointer<TESObjectREFR> GetGrabbedRef() { ++grabs; return grabbed.lock(); }
};
}
namespace logger { template<class... Args> void info(Args&&...) {} }

// Both included blocks are extracted verbatim from their respective Plugin.cpp.
void original(RE::Actor* topicActor, const std::function<void(RE::Actor&)>& observed) {
#include "original.inc"
}
void patched(RE::Actor* topicActor, const std::function<void(RE::Actor&)>& observed) {
#include "patched.inc"
}
void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}
struct Fixture {
    RE::CrosshairPickData pick;
    RE::PlayerCharacter player;
    Fixture() {
        RE::CrosshairPickData::instance = &pick;
        RE::PlayerCharacter::instance = &player;
        onTypeQuery = {};
    }
    ~Fixture() { onTypeQuery = {}; }
    void target(const std::shared_ptr<RE::TESObjectREFR>& object) {
        pick.target.state->id = 123;
        pick.target.state->object = object;
    }
};
int main() {
    try {
        {
            Fixture f;
            f.pick.target.state->id = 123; // non-zero ID, unresolved target
            unsigned observed = 0;
            const auto cb = [&](RE::Actor&) { ++observed; };
            bool reproduced = false;
            try { original(nullptr, cb); } catch (const NullReference&) { reproduced = true; }
            require(reproduced, "original must dereference the unresolved target");
            f.pick.target.state->resolves = 0;
            patched(nullptr, cb);
            require(observed == 0 && f.pick.target.state->resolves == 1, "patched stale ID must be skipped");
            std::cout << "PASS stale non-zero handle: original failure reproduced, patched safely skips\n";
        }
        {
            Fixture f;
            auto actor = std::make_shared<RE::Actor>();
            f.target(actor);
            unsigned observed = 0;
            patched(actor.get(), [&](RE::Actor&) { ++observed; });
            require(observed == 1 && f.pick.target.state->resolves == 1 && f.player.grabs == 0,
                    "valid crosshair actor must retain priority and resolve once");
            std::cout << "PASS valid crosshair actor and single resolution\n";
        }
        {
            Fixture f;
            auto actor = std::make_shared<RE::Actor>();
            f.pick.target.state->id = 123;
            f.player.grabbed = actor;
            unsigned observed = 0;
            patched(actor.get(), [&](RE::Actor&) { ++observed; });
            require(observed == 1 && f.player.grabs == 1, "unresolved target must allow retained grabbed fallback");
            std::cout << "PASS grabbed-reference fallback after failed resolution\n";
        }
        {
            Fixture f;
            auto object = std::make_shared<RE::TESObjectREFR>();
            f.target(object);
            unsigned observed = 0;
            patched(nullptr, [&](RE::Actor&) { ++observed; });
            require(observed == 0, "non-actor target must be rejected");
            std::cout << "PASS non-actor target rejection\n";
        }
        {
            Fixture f;
            auto actor = std::make_shared<RE::Actor>();
            auto speaker = std::make_shared<RE::Actor>();
            f.target(actor);
            unsigned observed = 0;
            patched(speaker.get(), [&](RE::Actor&) { ++observed; });
            require(observed == 0, "different speaker must be rejected");
            std::cout << "PASS speaker identity retained\n";
        }
        {
            Fixture f;
            RE::CrosshairPickData::instance = nullptr;
            RE::PlayerCharacter::instance = nullptr;
            unsigned observed = 0;
            patched(nullptr, [&](RE::Actor&) { ++observed; });
            require(observed == 0, "missing singletons must skip safely");
            std::cout << "PASS missing game singleton guards\n";
        }
        {
            bool oldFailed = false;
            for (bool usePatched : {false, true}) {
                Fixture f;
                auto actor = std::make_shared<RE::Actor>();
                const std::weak_ptr<RE::Actor> alive = actor;
                auto* speaker = actor.get();
                f.target(actor);
                onTypeQuery = [&] { actor.reset(); };
                unsigned observed = 0;
                const auto cb = [&](RE::Actor&) { require(!alive.expired(), "owner lost during use"); ++observed; };
                if (usePatched) {
                    patched(speaker, cb);
                    require(observed == 1 && f.pick.target.state->resolves == 1, "target must survive all callback uses");
                    require(alive.expired(), "retained target must be released after callback");
                } else {
                    try { original(speaker, cb); } catch (const NullReference&) { oldFailed = true; }
                }
            }
            require(oldFailed, "original repeated resolution must expose lifetime gap");
            std::cout << "PASS target lifetime retained through use, released afterward\n";
        }
        std::cout << "7 regression cases passed; game engine APIs were mocked, no Skyrim process launched\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL " << e.what() << '\n';
        return 1;
    }
}
