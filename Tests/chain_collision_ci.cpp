#include "Source/SKSE/GameBridgeContract.hpp"

#include <cassert>
#include <iostream>
#include <limits>

using namespace cms;

// Analytic collision oracle, independent of the solver's constraint code.
// A restricted link range represents a small obstacle at mid-chain height.
struct Plane {
    Vec3 normal{};
    float offset{};
    Vec3 velocity{};
    std::uintptr_t body{1};
    std::size_t first{}, last{63};
};
struct TestWorld : IChainCollisionQuery {
    std::vector<Plane> planes;
    unsigned batches{}, sweptCrossings{};
    float scale{1};
    bool invalid{};
    float chainCollisionScale() const override { return scale; }
    void queryChainContacts(const std::vector<ChainLinkSweep>& sweeps,
                            std::vector<ChainLinkContact>& out) override {
        ++batches;
        for (const auto& s : sweeps) {
            for (const auto& p : planes) {
                if (s.linkIndex < p.first || s.linkIndex > p.last) continue;
                const float fromSupport=s.radiusM+s.halfSegmentM*std::fabs(dot(s.fromAxis,p.normal));
                const float toSupport=s.radiusM+s.halfSegmentM*std::fabs(dot(s.toAxis,p.normal));
                const float from=dot(s.fromM,p.normal)-p.offset-fromSupport;
                const float to=dot(s.toM,p.normal)-p.offset-toSupport;
                if (from>0 && to<0) ++sweptCrossings;
                if (std::min(from,to) > .002f) continue;
                const Vec3 surface=s.fromM+p.normal*(p.offset-dot(s.fromM,p.normal));
                out.push_back({s.linkIndex,surface,p.normal,p.velocity,p.body});
            }
            if (invalid) {
                out.push_back({s.linkIndex,s.fromM,{0,0,0},{},1});
                out.push_back({s.linkIndex,s.fromM,{1,0,0},{1000,0,0},1});
                out.push_back({s.linkIndex,{std::numeric_limits<float>::quiet_NaN(),0,0},{1,0,0},{},1});
                out.push_back({s.linkIndex,s.fromM,{1,0,0},{},0});
                out.push_back({9999,s.fromM,{1,0,0},{},1});
            }
        }
    }
};

static float gap(const ChainSolver& s,std::size_t link,const Plane& p,float scale=1) {
    const auto& cfg=s.config();
    const float support=scale*(cfg.linkCollisionRadiusM+
        cfg.linkCollisionHalfSegmentM*std::fabs(dot(s.linkAxis(link),p.normal)));
    return dot(s.linkPosition(link),p.normal)-p.offset-support;
}

int main() {
    // Every appended link, including the new terminal link, follows exactly
    // the same query/response path. A wall touching only that link must bend
    // it without generating any head damage/drop contact.
    static_assert(kChainLinkCount==19);
    for(std::size_t added=14;added<19;++added) {
        ChainSolver longer;longer.reset({0,0,0});
        TestWorld contact;
        contact.planes={{{1,0,0},.025f,{},50+added,added,added}};
        for(int tick=0;tick<90;++tick){
            longer.step90Hz({0,0,0},&contact);
            assert(gap(longer,added,contact.planes[0])>=-.001f);
            assert(longer.activeContactCount()==0&&longer.lastContactPhysicsStep()==0);
        }
        assert(longer.linkPosition(added).x>.05f);
        assert(isFinite(longer.headPosition())&&length(longer.headVelocity90Hz())<5);
    }
    // Mid-chain contact bends the chain around a finite obstacle. It must
    // neither move the tracked hand nor create a head/attack contact sample.
    ChainSolver chain;
    const Vec3 anchor{0,0,0};
    chain.reset(anchor);
    TestWorld corner;
    corner.planes={{{1,0,0},.025f,{},1,6,8},{{0,1,0},.015f,{},2,6,8}};
    float worst=0;
    for (int step=0;step<180;++step) {
        chain.step90Hz(anchor,&corner);
        if (step==0) assert(chain.activeChainContactCount()>=2);
        assert(length(chain.anchorPosition()-anchor)==0);
        assert(chain.activeContactCount()==0 && chain.lastContactPhysicsStep()==0);
        for (std::size_t i=6;i<=8;++i) for (const auto& plane : corner.planes) {
            const float separation=gap(chain,i,plane);
            worst=std::min(worst,separation);
            assert(separation > -.001f);
            assert(isFinite(chain.linkVelocity90Hz(i)) && length(chain.linkVelocity90Hz(i))<20);
        }
    }
    assert(chain.linkPosition(7).x>.025f+chain.config().linkCollisionRadiusM-.001f && chain.linkPosition(7).y>.015f+chain.config().linkCollisionRadiusM-.001f);
    // Once that finite obstacle is removed there is no cached infinite plane.
    corner.planes.clear();
    chain.step90Hz(anchor,&corner);
    assert(chain.activeChainContactCount()==0);
    for(int step=0;step<360;++step) chain.step90Hz(anchor,&corner);
    assert(std::fabs(chain.linkPosition(7).x)<.03f);

    // A swept query catches a thin wall even when both end positions would
    // miss a discrete overlap test. This intentionally pulls the hand through
    // the wall: contacts take priority over impossible link-length constraints.
    ChainConfig one;
    one.linkCount=1;one.firstLinkCenterOffsetM=.4f;one.gravityMps2={};
    ChainSolver fast(one);fast.reset({-.7f,0,0},{1,0,0});
    TestWorld wall;wall.planes={{{-1,0,0},0,{},3}};
    fast.step90Hz({.6f,0,0},&wall);
    assert(wall.sweptCrossings>0);
    assert(gap(fast,0,wall.planes.front())>=-.001f);

    // A moving object displaces a stationary link, without launching it with
    // a velocity proportional to the depth of a late penetration correction.
    ChainSolver resting;resting.reset(anchor);
    TestWorld moving;moving.planes={{{1,0,0},-.04f,{.18f,0,0},4,7,7}};
    for(int step=0;step<60;++step) {
        moving.planes[0].offset+=.18f/90;
        resting.step90Hz(anchor,&moving);
        assert(gap(resting,7,moving.planes[0])>=-.001f);
        if (gap(resting,7,moving.planes[0])<.001f)
            assert(resting.linkVelocity90Hz(7).x>=.179f);
        assert(length(resting.linkVelocity90Hz(7))<5);
    }

    // The capsule follows the model scale, not a fixed unscaled width.
    ChainSolver scaled;scaled.reset(anchor);
    TestWorld small;small.scale=.85f;small.planes={{{1,0,0},0,{},5,7,7}};
    scaled.step90Hz(anchor,&small);
    assert(gap(scaled,7,small.planes[0],.85f)>=-.001f);
    assert(scaled.linkPosition(7).x<scaled.config().linkCollisionRadiusM);

    // Invalid native samples are rejected without poisoning the simulation.
    TestWorld malformed;malformed.invalid=true;
    const auto before=scaled.linkPosition(7);
    scaled.step90Hz(anchor,&malformed);
    assert(scaled.activeChainContactCount()==0);
    assert(isFinite(scaled.headPosition()) && length(scaled.linkPosition(7)-before)<1);
    scaled.reset(anchor);assert(scaled.activeChainContactCount()==0);

    // Contacts are queried for every 90 Hz step, independent of display rate.
    Vec3 reference{};
    float maxDelta=0;
    for(float hz : {90.0f,45.0f,72.0f,80.0f,120.0f,144.0f}) {
        FixedStepChain timed;timed.reset(anchor);
        TestWorld world;world.planes={{{1,0,0},.02f,{},6,6,8}};
        int ticks=0;
        for(int frame=1;frame<=static_cast<int>(hz*2);++frame)
            ticks+=timed.update(1/hz,{0,.1f*frame/hz,0},&world);
        assert(ticks==180 && world.batches>=180 && world.batches<=360);
        const auto final=timed.solver().headPosition();
        if(hz==90)reference=final;
        maxDelta=std::max(maxDelta,length(final-reference));
        assert(length(final-reference)<.001f);
    }
    std::cout<<"CMS chain-only collisions CI PASS\nworst_link_gap_m="<<worst
             <<"\n45_144_hz_chain_max_delta_m="<<maxDelta<<"\n";
}
