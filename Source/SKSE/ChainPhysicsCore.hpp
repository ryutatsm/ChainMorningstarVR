#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace cms {

constexpr float kSkyrimUnitsPerMeter = 69.99125f;
constexpr float kMetersPerSkyrimUnit = 1.0f / kSkyrimUnitsPerMeter;

struct Vec3 { float x{}, y{}, z{}; };

inline Vec3 operator+(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline Vec3 operator-(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline Vec3 operator-(Vec3 a) { return {-a.x, -a.y, -a.z}; }
inline Vec3 operator*(Vec3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
inline Vec3 operator*(float s, Vec3 a) { return a * s; }
inline Vec3 operator/(Vec3 a, float s) { return {a.x / s, a.y / s, a.z / s}; }
inline Vec3& operator+=(Vec3& a, Vec3 b) { a = a + b; return a; }
inline Vec3& operator-=(Vec3& a, Vec3 b) { a = a - b; return a; }

inline float dot(Vec3 a, Vec3 b) { return a.x*b.x + a.y*b.y + a.z*b.z; }
inline Vec3 cross(Vec3 a, Vec3 b) { return {a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x}; }
inline float lengthSq(Vec3 a) { return dot(a, a); }
inline float length(Vec3 a) { return std::sqrt(lengthSq(a)); }
inline Vec3 normalized(Vec3 a) { const float l = length(a); return l > 1.0e-7f ? a / l : Vec3{}; }
inline Vec3 lerp(Vec3 a, Vec3 b, float t) { return a + (b-a)*t; }

struct Particle {
    Vec3 position{};
    Vec3 previous{};
    float invMass{1.0f};
};

struct ChainConfig {
    std::size_t linkCount{14};
    float firstLinkCenterOffsetM{0.035f};
    float linkCenterSpanM{0.840f};
    float headCenterOffsetFromLastLinkM{0.190f};
    float linkMassKg{0.22f};
    float headMassKg{8.0f};
    float dampingPer90Hz{0.995f};
    int solverIterations{80};
    Vec3 gravityMps2{0.0f, 0.0f, -9.80665f};
};

class ChainSolver {
public:
    explicit ChainSolver(ChainConfig cfg = {}) : cfg_(sanitize(cfg)) { rebuildLayout(); }

    void reset(Vec3 anchor, Vec3 direction = {0.0f, 0.0f, -1.0f}) {
        direction = normalized(direction);
        if (lengthSq(direction) < 1.0e-7f) direction = {0.0f, 0.0f, -1.0f};
        points_[0].position = anchor;
        points_[0].previous = anchor;
        for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c) {
            const Vec3 p = points_[c].position + direction * constraintLengthsM_[c];
            points_[c + 1].position = p;
            points_[c + 1].previous = p;
        }
        initialized_ = true;
    }

    void teleport(Vec3 anchor, Vec3 direction = {0.0f, 0.0f, -1.0f}) { reset(anchor, direction); }

    void step90Hz(Vec3 anchor) {
        constexpr float dt = 1.0f / 90.0f;
        if (!initialized_) reset(anchor);
        const Vec3 oldAnchor = points_[0].position;
        points_[0].previous = oldAnchor;
        points_[0].position = anchor;
        const float damp = std::clamp(cfg_.dampingPer90Hz, 0.0f, 1.0f);
        for (std::size_t i = 1; i < points_.size(); ++i) {
            Particle& p = points_[i];
            const Vec3 velocity = (p.position - p.previous) * damp;
            p.previous = p.position;
            p.position += velocity + cfg_.gravityMps2 * (dt * dt);
        }
        const int iterations = std::max(1, cfg_.solverIterations);
        for (int iter = 0; iter < iterations; ++iter) {
            points_[0].position = anchor;
            if ((iter & 1) == 0) {
                for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c) solveDistance(c, c + 1, constraintLengthsM_[c]);
            } else {
                for (std::size_t c = constraintLengthsM_.size(); c-- > 0;) solveDistance(c, c + 1, constraintLengthsM_[c]);
            }
        }
        points_[0].position = anchor;
    }

    [[nodiscard]] const ChainConfig& config() const { return cfg_; }
    [[nodiscard]] const std::vector<Particle>& points() const { return points_; }
    [[nodiscard]] const std::vector<float>& constraintLengthsM() const { return constraintLengthsM_; }
    [[nodiscard]] std::size_t linkCount() const { return cfg_.linkCount; }
    [[nodiscard]] Vec3 anchorPosition() const { return points_.front().position; }
    [[nodiscard]] Vec3 linkPosition(std::size_t i) const { return points_.at(i + 1).position; }
    [[nodiscard]] Vec3 headPosition() const { return points_.back().position; }

    [[nodiscard]] Vec3 linkVelocity90Hz(std::size_t i) const {
        constexpr float invDt = 90.0f;
        const Particle& p = points_.at(i + 1);
        return (p.position - p.previous) * invDt;
    }
    [[nodiscard]] Vec3 headVelocity90Hz() const {
        constexpr float invDt = 90.0f;
        return (points_.back().position - points_.back().previous) * invDt;
    }

    [[nodiscard]] float straightReachM() const {
        float s = 0.0f;
        for (float l : constraintLengthsM_) s += l;
        return s;
    }

    [[nodiscard]] float maxConstraintErrorM() const {
        float e = 0.0f;
        for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c) {
            const float d = length(points_[c + 1].position - points_[c].position);
            e = std::max(e, std::fabs(d - constraintLengthsM_[c]));
        }
        return e;
    }

private:
    static ChainConfig sanitize(ChainConfig cfg) {
        cfg.linkCount = std::max<std::size_t>(1, cfg.linkCount);
        cfg.firstLinkCenterOffsetM = std::max(0.001f, cfg.firstLinkCenterOffsetM);
        cfg.linkCenterSpanM = std::max(0.0f, cfg.linkCenterSpanM);
        cfg.headCenterOffsetFromLastLinkM = std::max(0.001f, cfg.headCenterOffsetFromLastLinkM);
        cfg.linkMassKg = std::max(0.001f, cfg.linkMassKg);
        cfg.headMassKg = std::max(0.001f, cfg.headMassKg);
        cfg.solverIterations = std::max(1, cfg.solverIterations);
        return cfg;
    }

    void rebuildLayout() {
        points_.assign(cfg_.linkCount + 2, {});
        points_[0].invMass = 0.0f;
        for (std::size_t i = 0; i < cfg_.linkCount; ++i) points_[i + 1].invMass = 1.0f / cfg_.linkMassKg;
        points_.back().invMass = 1.0f / cfg_.headMassKg;
        constraintLengthsM_.clear();
        constraintLengthsM_.reserve(cfg_.linkCount + 1);
        constraintLengthsM_.push_back(cfg_.firstLinkCenterOffsetM);
        if (cfg_.linkCount > 1) {
            const float centreSpacing = cfg_.linkCenterSpanM / static_cast<float>(cfg_.linkCount - 1);
            for (std::size_t i = 1; i < cfg_.linkCount; ++i) constraintLengthsM_.push_back(centreSpacing);
        }
        constraintLengthsM_.push_back(cfg_.headCenterOffsetFromLastLinkM);
    }

    void solveDistance(std::size_t ia, std::size_t ib, float restLength) {
        Particle& a = points_[ia];
        Particle& b = points_[ib];
        const Vec3 delta = b.position - a.position;
        const float dist = length(delta);
        if (dist < 1.0e-7f) return;
        const float w0 = a.invMass;
        const float w1 = b.invMass;
        const float ws = w0 + w1;
        if (ws <= 0.0f) return;
        const Vec3 correction = delta * ((dist - restLength) / dist);
        if (w0 > 0.0f) a.position += correction * (w0 / ws);
        if (w1 > 0.0f) b.position -= correction * (w1 / ws);
    }

    ChainConfig cfg_{};
    std::vector<Particle> points_{};
    std::vector<float> constraintLengthsM_{};
    bool initialized_{false};
};

class FixedStepChain {
public:
    explicit FixedStepChain(ChainConfig cfg = {}) : solver_(cfg) {}

    void reset(Vec3 anchor, Vec3 direction = {0,0,-1}) {
        accumulator_ = 0.0f;
        solver_.reset(anchor, direction);
        lastInputAnchor_ = anchor;
        hasInputAnchor_ = true;
    }

    int update(float frameDt, Vec3 anchor) {
        frameDt = std::clamp(frameDt, 0.0f, 0.05f);
        if (!hasInputAnchor_) { lastInputAnchor_ = anchor; hasInputAnchor_ = true; }
        if (frameDt <= 0.0f) { lastInputAnchor_ = anchor; return 0; }
        constexpr float h = 1.0f / 90.0f;
        const float accumulatorAtFrameStart = accumulator_;
        accumulator_ += frameDt;
        int steps = 0;
        float sampleTimeInFrame = h - accumulatorAtFrameStart;
        while (accumulator_ >= h && steps < 5) {
            const float alpha = std::clamp(sampleTimeInFrame / frameDt, 0.0f, 1.0f);
            solver_.step90Hz(lerp(lastInputAnchor_, anchor, alpha));
            accumulator_ -= h;
            sampleTimeInFrame += h;
            ++steps;
        }
        if (steps == 5 && accumulator_ >= h) accumulator_ = 0.0f;
        lastInputAnchor_ = anchor;
        return steps;
    }

    [[nodiscard]] ChainSolver& solver() { return solver_; }
    [[nodiscard]] const ChainSolver& solver() const { return solver_; }
    [[nodiscard]] float accumulatorSeconds() const { return accumulator_; }

private:
    ChainSolver solver_;
    Vec3 lastInputAnchor_{};
    float accumulator_{};
    bool hasInputAnchor_{};
};

struct SweepHit { bool hit{false}; float t{1.0f}; Vec3 point{}; };

inline SweepHit sweptSphereVsSphere(Vec3 start, Vec3 end, float movingRadius,
                                    Vec3 targetCenter, float targetRadius) {
    const float r = movingRadius + targetRadius;
    const Vec3 v = end - start;
    const Vec3 m = start - targetCenter;
    const float c = dot(m,m) - r*r;
    if (c <= 0.0f) return {true, 0.0f, start};
    const float a = dot(v,v);
    if (a < 1.0e-10f) return {};
    const float b = dot(m,v);
    if (b > 0.0f) return {};
    const float disc = b*b - a*c;
    if (disc < 0.0f) return {};
    const float t = std::clamp((-b - std::sqrt(disc)) / a, 0.0f, 1.0f);
    return {true, t, lerp(start,end,t)};
}

inline float chainExtension(const ChainSolver& s) { return length(s.headPosition() - s.anchorPosition()); }

} // namespace cms
