#pragma once

#include <cstdint>
#include "ChainRuntimeCore.hpp"

namespace cms {

class IGameBridge {
public:
    virtual ~IGameBridge() = default;
    virtual bool tryGetChainAnchorWorldSU(Vec3& outPositionSU, Vec3& outInitialDirectionWorld) = 0;
    virtual bool reacquireWeaponNodes() = 0;
    virtual void releaseWeaponNodes() = 0;
    virtual void applyVisualFrame(const VisualFrame& frame) = 0;
    virtual bool updateNativeMeleeHeadProxy(const HeadSweep& sweep) = 0;
    virtual float consumeWorldContactImpulse() = 0;
    virtual void playChainRattle(float intensity) = 0;
    virtual void playChainClank(float intensity) = 0;
};

class RuntimeDriver {
public:
    explicit RuntimeDriver(IGameBridge& bridge) : bridge_(bridge) {}

    void onEquip() {
        Vec3 anchor{}, direction{0,0,-1};
        if (!bridge_.reacquireWeaponNodes()) return;
        if (!bridge_.tryGetChainAnchorWorldSU(anchor, direction)) return;
        controller_.onEquip(anchor, direction);
        active_ = true;
    }

    void onUnequip() {
        controller_.onUnequip();
        bridge_.releaseWeaponNodes();
        active_ = false;
    }

    void update(float frameDt) {
        if (!active_) return;
        Vec3 anchor{}, direction{};
        if (!bridge_.tryGetChainAnchorWorldSU(anchor, direction)) {
            onUnequip();
            return;
        }
        if (!controller_.update(frameDt, anchor)) return;
        const VisualFrame frame = controller_.visualFrame();
        bridge_.applyVisualFrame(frame);
        bridge_.updateNativeMeleeHeadProxy(controller_.headSweep());
        const float impulse = bridge_.consumeWorldContactImpulse();
        const ChainSoundEvent ev = controller_.soundEvent(frameDt, impulse);
        if (ev.type == ChainSoundEventType::kRattle) bridge_.playChainRattle(ev.intensity);
        if (ev.type == ChainSoundEventType::kHeavyClank) bridge_.playChainClank(ev.intensity);
    }

    [[nodiscard]] bool active() const { return active_; }
    [[nodiscard]] ChainController& controller() { return controller_; }

private:
    IGameBridge& bridge_;
    ChainController controller_{};
    bool active_{};
};

} // namespace cms
