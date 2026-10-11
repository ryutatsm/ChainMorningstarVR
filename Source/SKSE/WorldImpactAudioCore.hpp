#pragma once
#include "ChainPhysicsCore.hpp"
#include <array>

namespace cms {
struct WorldImpactSound { float intensity{}; Vec3 pointM{}; float closingSpeedMps{}; };
// Audio only: incoming native/sweep velocity, before collision response.
// Never derive sound from solver depenetration or change the physics state.
class WorldImpactAudioGate {
public:
    void reset() { *this = {}; }
    WorldImpactSound update(float dt, const std::vector<HeadWorldContact>& contacts) {
        if (!std::isfinite(dt) || dt <= 0) return {};
        dt = std::min(dt, .05f);
        cooldown_ = std::max(0.0f, cooldown_ - dt);
        for (auto& e : episodes_) { e.absentS += dt; if (e.absentS > .08f) e = {}; }
        const auto previousStep = lastStep_;
        ++batch_;
        WorldImpactSound best{};
        for (const auto& c : contacts) {
            if (!c.physicsStep || c.physicsStep <= previousStep || !c.otherBodyIdentity ||
                !isFinite(c.normalWorld) || !isFinite(c.headVelocityMps) ||
                !isFinite(c.surfaceVelocityMps) || !isFinite(c.pointM) ||
                !std::isfinite(c.signedDistanceM) || c.signedDistanceM > .005f ||
                lengthSq(c.normalWorld) < .25f) continue;
            lastStep_ = std::max(lastStep_, c.physicsStep);
            const auto normal = normalized(c.normalWorld);
            Episode* episode = nullptr;
            for (auto& e : episodes_) {
                if (e.body == c.otherBodyIdentity && dot(e.normal, normal) > .9f) { episode = &e; break; }
            }
            if (!episode) {
                for (auto& e : episodes_) if (!e.body) { episode = &e; break; }
                if (!episode) continue;
                *episode = {c.otherBodyIdentity, normal, 0, false, 0};
            }
            episode->absentS = 0;
            const float closing = -dot(c.headVelocityMps - c.surfaceVelocityMps, normal);
            if (!std::isfinite(closing)) continue;
            if (closing < -.25f) episode->played = false;
            if (closing < .65f || (episode->played && episode->triggerBatch != batch_)) continue;
            episode->played = true;
            episode->triggerBatch = batch_;
            if (closing > best.closingSpeedMps)
                best = {std::clamp(.45f + (closing - .65f) * .12f, .45f, 1.0f), c.pointM, closing};
        }
        if (best.intensity <= 0 || cooldown_ > 0) return {};
        cooldown_ = .18f;
        return best;
    }
private:
    struct Episode { std::uintptr_t body{}; Vec3 normal{}; float absentS{}; bool played{}; std::uint64_t triggerBatch{}; };
    std::array<Episode, 32> episodes_{};
    std::uint64_t lastStep_{};
    std::uint64_t batch_{};
    float cooldown_{};
};
} // namespace cms
