#pragma once
#include "ChainPhysicsCore.hpp"

namespace cms {
struct BodyCapsule {
    Vec3 previousA{}, previousB{}, a{}, b{};
    float radiusM{};
    std::uintptr_t identity{};
};

struct SegmentPair {
    Vec3 p{}, q{};
    float bodyT{};
};
inline SegmentPair closestSegments(Vec3 p0,Vec3 p1,Vec3 q0,Vec3 q1) {
    const Vec3 u=p1-p0,v=q1-q0,w=p0-q0;
    const float a=dot(u,u),b=dot(u,v),c=dot(v,v),d=dot(u,w),e=dot(v,w);
    float s=0,t=0;
    if (a<1e-10f && c<1e-10f) return {p0,q0,0};
    if (a<1e-10f) t=std::clamp(e/c,0.0f,1.0f);
    else if (c<1e-10f) s=std::clamp(-d/a,0.0f,1.0f);
    else {
        const float denom=a*c-b*b;
        if (denom>1e-10f) s=std::clamp((b*e-c*d)/denom,0.0f,1.0f);
        t=(b*s+e)/c;
        if (t<0) {t=0;s=std::clamp(-d/a,0.0f,1.0f);}
        else if (t>1) {t=1;s=std::clamp((b-d)/a,0.0f,1.0f);}
    }
    return {p0+u*s,q0+v*t,t};
}

// Continuous relative sweep of two capsule centre segments. Only produces
// solver planes: never inserts a player/attack rigidbody into Havok.
inline void queryPlayerBodyContacts(const std::vector<ChainLinkSweep>& sweeps,
    const std::vector<BodyCapsule>& bodies, float frameDt,
    std::vector<ChainLinkContact>& contacts) {
    if (!std::isfinite(frameDt)||frameDt<=0) return;
    for (const auto& s:sweeps) {
        if (!isFinite(s.fromM)||!isFinite(s.toM)||!isFinite(s.fromAxis)||!isFinite(s.toAxis)||
            !std::isfinite(s.radiusM)||!std::isfinite(s.halfSegmentM)||s.radiusM<=0||s.halfSegmentM<0) continue;
        Vec3 oldAxis=normalized(s.fromAxis),newAxis=normalized(s.toAxis);
        if (lengthSq(oldAxis)<.5f||lengthSq(newAxis)<.5f) continue;
        if (dot(oldAxis,newAxis)<0) newAxis=-newAxis;
        const Vec3 p0=s.fromM-oldAxis*s.halfSegmentM,p1=s.fromM+oldAxis*s.halfSegmentM;
        const Vec3 end0=s.toM-newAxis*s.halfSegmentM,end1=s.toM+newAxis*s.halfSegmentM;
        for (const auto& b:bodies) {
            if (!b.identity||!std::isfinite(b.radiusM)||b.radiusM<=0||b.radiusM>.5f||
                !isFinite(b.a)||!isFinite(b.b)||!isFinite(b.previousA)||!isFinite(b.previousB)) continue;
            const float margin=s.radiusM+b.radiusM+.001f;
            const auto separate=[&](float p,float q,float r,float u,float a,float c,float d,float e) {
                return std::max({p,q,r,u})+margin<std::min({a,c,d,e}) ||
                    std::min({p,q,r,u})-margin>std::max({a,c,d,e});
            };
            if (separate(p0.x,p1.x,end0.x,end1.x,b.a.x,b.b.x,b.previousA.x,b.previousB.x)||
                separate(p0.y,p1.y,end0.y,end1.y,b.a.y,b.b.y,b.previousA.y,b.previousB.y)||
                separate(p0.z,p1.z,end0.z,end1.z,b.a.z,b.b.z,b.previousA.z,b.previousB.z)) continue;
            const float speedBound=std::max(length(end0-p0),length(end1-p1))+
                std::max(length(b.a-b.previousA),length(b.b-b.previousB));
            float t=0;SegmentPair pair{};bool hit=false;
            for (int iteration=0;iteration<48;++iteration) {
                pair=closestSegments(lerp(p0,end0,t),lerp(p1,end1,t),
                    lerp(b.previousA,b.a,t),lerp(b.previousB,b.b,t));
                const float gap=length(pair.p-pair.q)-s.radiusM-b.radiusM;
                if (gap<=.0005f) {hit=true;break;}
                if (speedBound<1e-7f) break;
                const float next=t+gap/speedBound;
                if (next>1) break;
                t=next;
            }
            if (!hit) {
                pair=closestSegments(end0,end1,b.a,b.b);
                hit=length(pair.p-pair.q)<=s.radiusM+b.radiusM+.0005f;
            }
            if (!hit) continue;
            Vec3 normal=normalized(pair.p-pair.q);
            if (lengthSq(normal)<.5f) normal=normalized(s.fromM-(b.previousA+b.previousB)*.5f);
            if (lengthSq(normal)<.5f) normal={1,0,0};
            const Vec3 surface=lerp(b.a,b.b,pair.bodyT)+normal*b.radiusM;
            Vec3 velocity=(lerp(b.a,b.b,pair.bodyT)-lerp(b.previousA,b.previousB,pair.bodyT))/frameDt;
            if (lengthSq(velocity)>100.0f) velocity=normalized(velocity)*10.0f;
            contacts.push_back({s.linkIndex,surface,normal,velocity,b.identity});
        }
    }
}
} // namespace cms
