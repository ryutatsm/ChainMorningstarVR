#include "Source/SKSE/ChainPhysicsCore.hpp"
#include "Source/SKSE/ChainRuntimeCore.hpp"
#include "Source/SKSE/SceneTransformCore.hpp"
#include "Source/SKSE/NativeMeleeDataProbeCore.hpp"
#include "Source/SKSE/HeadCompoundCore.hpp"
#include "Source/SKSE/NativeProxyOwnershipCore.hpp"
#include "Source/SKSE/GameBridgeContract.hpp"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

static bool nearf(float a, float b, float eps) { return std::fabs(a-b) <= eps; }

struct LifecycleBridge final : cms::IGameBridge {
    bool acquireSucceeds{true};
    bool anchorSucceeds{true};
    bool retainsNodes{};
    int framesApplied{};
    cms::Vec3 anchor{};

    bool tryGetChainAnchorWorldSU(cms::Vec3& out, cms::Vec3& direction) override {
        out=anchor;
        direction={0,0,-1};
        return anchorSucceeds;
    }
    bool reacquireWeaponNodes() override {
        // Exercise failure after partial scene-node acquisition, too.
        retainsNodes=true;
        return acquireSucceeds;
    }
    void releaseWeaponNodes() override { retainsNodes=false; }
    void applyVisualFrame(const cms::VisualFrame&) override {
        assert(retainsNodes);
        ++framesApplied;
    }
    bool updateNativeMeleeHeadProxy(const cms::HeadSweep&) override { return false; }
    float consumeWorldContactImpulse() override { return 0; }
    void playChainRattle(float) override {}
    void playChainClank(float) override {}
};

int main()
{
    using namespace cms;

    ChainSolver solver{};
    solver.reset({0,0,0}, {0,0,-1});
    assert(solver.linkCount() == 19);
    assert(nearf(solver.straightReachM(), 1.0410576923f, 1.0e-5f));

    // Static gravity settling: constraints must remain tight.
    for (int i=0; i<180; ++i) solver.step90Hz({0,0,0});
    assert(solver.maxConstraintErrorM() < 0.004f);

    // Render-rate independence: same 0.45m/0.2s controller trajectory sampled at 45 vs 90 Hz.
    auto simulate = [](float renderHz) {
        FixedStepChain chain{};
        chain.reset({0,0,0}, {0,0,-1});
        const float duration=0.2f;
        const int frames=static_cast<int>(duration*renderHz+0.5f);
        for (int i=1;i<=frames;++i) {
            const float t=static_cast<float>(i)/static_cast<float>(frames);
            chain.update(1.0f/renderHz, {0.45f*t,0,0});
        }
        return chain.solver().headPosition();
    };

    const Vec3 p45=simulate(45.0f);
    const Vec3 p90=simulate(90.0f);
    assert(length(p45-p90) < 0.003f);

    // Real Quest/PCVR frame rates must not lose a physics tick to float clock drift.
    Vec3 referenceAtTwoSeconds{};
    for (float hz : {90.0f,45.0f,72.0f,80.0f,120.0f,144.0f}) {
        FixedStepChain chain{};
        chain.reset({0,0,0});
        int steps=0;
        for (int i=1; i<=static_cast<int>(hz*2.0f); ++i)
            steps += chain.update(1.0f/hz,{0.5f*static_cast<float>(i)/hz,0,0});
        assert(steps==180);
        if (hz==90.0f) referenceAtTwoSeconds=chain.solver().headPosition();
        assert(length(chain.solver().headPosition()-referenceAtTwoSeconds)<0.0001f);
    }

    // Segment sweep regression: a ray hit past this frame's endpoint is not a hit.
    assert(!sweptSphereVsSphere({0,0,0},{1,0,0},0.1f,{4,0,0},0.1f).hit);
    assert(!sweptSphereVsSphere({0,0,0},{1,0,0},0.1f,{-1,0,0},0.1f).hit);
    assert(!sweptSphereVsSphere({0,0,0},{0,0,0},0.1f,{1,0,0},0.1f).hit);
    const auto contact=sweptSphereVsSphere({0,0,0},{2,0,0},0.25f,{1,0,0},0.25f);
    assert(contact.hit && nearf(contact.t,0.25f,1.0e-6f));
    assert(nearf(contact.point.x,0.5f,1.0e-6f));
    const auto endpoint=sweptSphereVsSphere({0,0,0},{1,0,0},0.25f,{1.5f,0,0},0.25f);
    assert(endpoint.hit && nearf(endpoint.t,1.0f,1.0e-6f));
    const auto tangent=sweptSphereVsSphere({-1,0,0},{1,0,0},0.25f,{0,0.5f,0},0.25f);
    assert(tangent.hit && nearf(tangent.t,0.5f,1.0e-6f));
    const auto overlap=sweptSphereVsSphere({0,0,0},{-1,0,0},0.25f,{0.1f,0,0},0.25f);
    assert(overlap.hit && overlap.t==0.0f);
    assert(!sweptSphereVsSphere({0,0,0},{1,0,0},-0.1f,{0.5f,0,0},0.1f).hit);

    const float nan=std::numeric_limits<float>::quiet_NaN();
    const float inf=std::numeric_limits<float>::infinity();
    assert(!sweptSphereVsSphere({nan,0,0},{1,0,0},0.1f,{0.5f,0,0},0.1f).hit);
    FixedStepChain resilient{};
    resilient.reset({0,0,0});
    const Vec3 beforeBadSample=resilient.solver().headPosition();
    assert(resilient.update(nan,{0,0,0})==0);
    assert(resilient.update(1.0f/90.0f,{inf,0,0})==0);
    assert(length(resilient.solver().headPosition()-beforeBadSample)==0.0f);
    assert(resilient.update(1.0f/90.0f,{0,0,0})==1);
    assert(isFinite(resilient.solver().headPosition()));

    // A weapon scene can detach between reacquire and anchor read. The old
    // driver leaked its retained nodes/proxy and stayed active on re-equip failure.
    LifecycleBridge bridge{};
    RuntimeDriver driver{bridge};
    driver.onEquip();
    assert(driver.active() && bridge.retainsNodes);
    driver.update(1.0f/90.0f);
    assert(bridge.framesApplied==1);
    driver.update(0.0f);
    driver.update(nan);
    assert(bridge.framesApplied==1);
    bridge.anchorSucceeds=false;
    driver.onEquip();
    assert(!driver.active() && !driver.controller().equipped() && !bridge.retainsNodes);
    driver.update(1.0f/90.0f);
    assert(bridge.framesApplied==1);
    bridge.anchorSucceeds=true;
    bridge.acquireSucceeds=false;
    driver.onEquip();
    assert(!driver.active() && !bridge.retainsNodes);
    bridge.acquireSucceeds=true;
    bridge.anchor={nan,0,0};
    driver.onEquip();
    assert(!driver.active() && !bridge.retainsNodes);
    bridge.anchor={0,0,0};
    driver.onEquip();
    assert(driver.active() && bridge.retainsNodes);
    bridge.anchorSucceeds=false;
    driver.update(0.0f); // even paused unequip must release ownership
    assert(!driver.active() && !bridge.retainsNodes);

    ChainController controller{};
    controller.onEquip({0,0,0},{0,0,-1});
    for(int i=0;i<10;++i) controller.update(1.0f/90.0f,{0,0,0});
    auto visual=controller.visualFrame();
    assert(visual.links.size()==19);
    auto sweep=controller.headSweep();
    assert(nearf(sweep.radiusM,0.24f*kModelScale,1.0e-6f));
    assert(!controller.update(nan,{0,0,0}));
    assert(controller.headSweep().speedMps==0.0f);
    assert(controller.update(1.0f/90.0f,{0,0,0}));
    // Fast travel must relocate without producing a damage sweep across the world.
    assert(controller.update(1.0f/90.0f,{1000,0,0}));
    sweep=controller.headSweep();
    assert(sweep.speedMps==0.0f && length(sweep.toM-sweep.fromM)==0.0f);

    // New-build head geometry: 12 cm core + 14 explicit spikes, each reaching 18 cm.
    HeadPose hp{};
    hp.centerM={0,0,0};
    hp.chainAxis={0,0,1};
    const auto compound=buildHeadCompoundFrame(hp);
    static_assert(kSpikeCount==14);
    assert(nearf(compound.coreRadiusM,0.16f*kModelScale,1.0e-6f));
    assert(nearf(compound.broadphaseRadiusM,0.24f*kModelScale,1.0e-6f));
    for (const auto& sp:compound.spikes) {
        assert(nearf(length(sp.tipM-compound.coreCenterM),0.24f*kModelScale,1.0e-5f));
        assert(nearf(length(sp.baseCenterM-compound.coreCenterM),0.154f*kModelScale,1.0e-5f));
    }
    assert(nearf(supportDistanceAlongRay(compound,{1,0,0}),0.24f*kModelScale*kRimCos,1.0e-5f));
    assert(nearf(supportDistanceAlongRay(compound,{-1,0,0}),0.24f*kModelScale*kRimCos,1.0e-5f));
    assert(nearf(supportDistanceAlongRay(compound,{0,1,0}),0.16f*kModelScale,1.0e-5f));
    assert(nearf(supportDistanceAlongRay(compound,{0,0,1}),0.24f*kModelScale*kRimCos,1.0e-5f));
    for (Vec3 direction:kSpikeDirectionsLocal) {
        assert(nearf(length(direction),1.0f,1.0e-6f));
        assert(nearf(supportDistanceAlongRay(compound,direction),0.24f*kModelScale,1.0e-5f));
    }

    // A cone cannot inherit the base disk radius at its tip. This used to inflate
    // the support for oblique queries by centimetres.
    HeadCompoundFrame singleCone{};
    for (auto& spike:singleCone.spikes)
        spike={{1,0,0},{kSpikeInnerAxisM,0,0},{kSpikeOuterAxisM,0,0},kSpikeBaseRadiusM};
    assert(nearf(supportDistanceAlongRay(singleCone,{1,0,1}),
        kSpikeOuterAxisM/std::sqrt(2.0f),1.0e-6f));

    const Mat3 basis=basisFromLocalZ({0.3f,0.4f,0.8660254f},0.7f);
    assert(approximatelyOrthonormal(basis,1.0e-4f));

    // Ownership behavior derived from the target runtime log: native collisionNode can
    // legitimately change between samples, so CMS must not overwrite an external value.
    constexpr std::uintptr_t playerA=0x1000;
    constexpr std::uintptr_t playerB=0x2000;
    constexpr std::uintptr_t cmsHead=0x3000;
    constexpr std::uintptr_t externalA=0x4000;
    constexpr std::uintptr_t externalB=0x5000;

    static_assert(evaluateNativeProxyOwnership(
        {false,playerA,playerA,cmsHead,cmsHead}) == NativeProxyOwnershipState::kInactive);
    static_assert(evaluateNativeProxyOwnership(
        {true,playerA,playerA,cmsHead,cmsHead}) == NativeProxyOwnershipState::kOwnedByCms);
    static_assert(evaluateNativeProxyOwnership(
        {true,playerA,playerB,cmsHead,cmsHead}) == NativeProxyOwnershipState::kPlayerChanged);
    static_assert(evaluateNativeProxyOwnership(
        {true,playerA,playerA,cmsHead,externalA}) == NativeProxyOwnershipState::kCollisionChanged);
    static_assert(evaluateNativeProxyOwnership(
        {true,playerA,playerA,cmsHead,externalB}) == NativeProxyOwnershipState::kCollisionChanged);

    static_assert(sizeof(NativeVRMeleeDataProbeLayout)==0xD0);
    static_assert(offsetof(NativeVRMeleeDataProbeLayout, collisionNode)==0x18);
    static_assert(offsetof(NativeVRMeleeDataProbeLayout, linearVelocityThreshold)==0xA4);

    // Regression from the 0.4.1 target log: PLANCK's internal offsetNode was
    // consistently +0x300 from CommonLib's named MeleeWeaponOffsetNode. That
    // identity mismatch is diagnostic metadata only and must not reject the
    // otherwise-plausible PLANCK VRMeleeData layout.
    NativeVRMeleeDataProbeLayout targetLogLike{};
    targetLogLike.world = 0x1000;
    targetLogLike.collisionNode = 0x2000;
    constexpr std::uintptr_t expectedNamedOffset = 0x5000;
    targetLogLike.offsetNode = expectedNamedOffset + 0x300;
    targetLogLike.linearVelocityThreshold = 2.0f;
    targetLogLike.enableCollision = 0;
    targetLogLike.applyImpulseOnHit = 1;
    targetLogLike.swingDirection = 0;
    targetLogLike.cooldown = 0.0f;
    targetLogLike.duration = 0.0f;

    const auto mismatchProbe = inspectNativeMeleeDataReadOnly(targetLogLike, expectedNamedOffset);
    assert(mismatchProbe.plausible());
    assert(!mismatchProbe.offsetMatchesExpected);

    // The named CommonLib node may be unavailable; it is not needed to validate
    // PLANCK's own non-null offsetNode.
    const auto noExpectedProbe = inspectNativeMeleeDataReadOnly(targetLogLike, 0);
    assert(noExpectedProbe.plausible());
    assert(!noExpectedProbe.offsetMatchesExpected);

    targetLogLike.swingDirection = 2; // not a valid Skyrim VR SwingDirection value
    assert(inspectNativeMeleeDataReadOnly(targetLogLike, expectedNamedOffset).status ==
           NativeMeleeProbeStatus::kInvalidSwingDirection);
    targetLogLike.swingDirection = 0;

    targetLogLike.cooldown = -0.25f; // engine timers may run below zero
    assert(inspectNativeMeleeDataReadOnly(targetLogLike, expectedNamedOffset).plausible());
    targetLogLike.cooldown = nan;
    assert(inspectNativeMeleeDataReadOnly(targetLogLike, expectedNamedOffset).status ==
           NativeMeleeProbeStatus::kInvalidTimers);
    targetLogLike.cooldown = 0.0f;
    targetLogLike.duration = inf;
    assert(inspectNativeMeleeDataReadOnly(targetLogLike, expectedNamedOffset).status ==
           NativeMeleeProbeStatus::kInvalidTimers);
    targetLogLike.duration = 0.0f;

    std::cout << "CMS core CI PASS\n";
    std::cout << "reach_m=" << solver.straightReachM() << "\n";
    std::cout << "constraint_error_m=" << solver.maxConstraintErrorM() << "\n";
    std::cout << "45_90_head_delta_m=" << length(p45-p90) << "\n";
    return 0;
}
