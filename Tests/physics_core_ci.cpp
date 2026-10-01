#include "Source/SKSE/ChainPhysicsCore.hpp"
#include "Source/SKSE/ChainRuntimeCore.hpp"
#include "Source/SKSE/SceneTransformCore.hpp"
#include "Source/SKSE/NativeMeleeDataProbeCore.hpp"
#include "Source/SKSE/HeadCompoundCore.hpp"

#include <cassert>
#include <cmath>
#include <iostream>

static bool nearf(float a, float b, float eps) { return std::fabs(a-b) <= eps; }

int main()
{
    using namespace cms;

    ChainSolver solver{};
    solver.reset({0,0,0}, {0,0,-1});
    assert(solver.linkCount() == 14);
    assert(nearf(solver.straightReachM(), 1.065f, 1.0e-5f));

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

    ChainController controller{};
    controller.onEquip({0,0,0},{0,0,-1});
    for(int i=0;i<10;++i) controller.update(1.0f/90.0f,{0,0,0});
    auto visual=controller.visualFrame();
    assert(visual.links.size()==14);
    auto sweep=controller.headSweep();
    assert(nearf(sweep.radiusM,0.24f,1.0e-6f));

    // New-build head geometry: 16 cm core + 14 explicit spikes, each reaching 24 cm.
    HeadPose hp{};
    hp.centerM={0,0,0};
    hp.chainAxis={0,0,1};
    const auto compound=buildHeadCompoundFrame(hp);
    static_assert(kSpikeCount==14);
    assert(nearf(compound.coreRadiusM,0.16f,1.0e-6f));
    assert(nearf(compound.broadphaseRadiusM,0.24f,1.0e-6f));
    for (const auto& sp:compound.spikes) {
        assert(nearf(length(sp.tipM-compound.coreCenterM),0.24f,1.0e-5f));
        assert(nearf(length(sp.baseCenterM-compound.coreCenterM),0.154f,1.0e-5f));
    }
    assert(nearf(supportDistanceAlongRay(compound,{1,0,0}),0.24f,1.0e-5f));
    assert(nearf(supportDistanceAlongRay(compound,{-1,0,0}),0.24f,1.0e-5f));
    assert(nearf(supportDistanceAlongRay(compound,{0,1,0}),0.24f,1.0e-5f));
    assert(nearf(supportDistanceAlongRay(compound,{0,0,1}),0.24f,1.0e-5f));

    const Mat3 basis=basisFromLocalZ({0.3f,0.4f,0.8660254f},0.7f);
    assert(approximatelyOrthonormal(basis,1.0e-4f));

    static_assert(sizeof(NativeVRMeleeDataProbeLayout)==0xD0);
    static_assert(offsetof(NativeVRMeleeDataProbeLayout, collisionNode)==0x18);
    static_assert(offsetof(NativeVRMeleeDataProbeLayout, linearVelocityThreshold)==0xA4);

    std::cout << "CMS core CI PASS\n";
    std::cout << "reach_m=" << solver.straightReachM() << "\n";
    std::cout << "constraint_error_m=" << solver.maxConstraintErrorM() << "\n";
    std::cout << "45_90_head_delta_m=" << length(p45-p90) << "\n";
    return 0;
}
