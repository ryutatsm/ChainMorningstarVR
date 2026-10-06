#pragma once

#include "HeadContactPlanes.hpp"
#include "SceneTransformCore.hpp"
#include <array>
#include <algorithm>
#include <cmath>

namespace cms::weaponmesh {

struct Triangle { std::array<Vec3, 3> vertices; };
struct Contact { bool hit{}; Vec3 pointM{}; float time{}; };

inline bool finite(Vec3 p) { return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z); }
inline bool valid(const RigidTransform& t) {
    return finite(t.translation) && std::isfinite(t.scale) && t.scale > 0.001f &&
        t.scale < 100.0f && approximatelyOrthonormal(t.rotation, .003f);
}

// Clip the actual triangle against each native convex hull. No head/hand
// distance, support-plane projection or enclosing sphere can certify a hit.
inline Contact intersectHeadLocal(const Triangle& tri) {
    Contact out{};
    for (const auto& p : tri.vertices) if (!finite(p)) return out;
    if (lengthSq(cross(tri.vertices[1]-tri.vertices[0], tri.vertices[2]-tri.vertices[0])) < 1e-18f) return out;
    for (int axis=0; axis<3; ++axis) {
        const auto value=[axis](Vec3 p) { return axis==0 ? p.x : axis==1 ? p.y : p.z; };
        float lo=value(tri.vertices[0]), hi=lo;
        for (int v=1; v<3; ++v) { lo=std::min(lo,value(tri.vertices[v])); hi=std::max(hi,value(tri.vertices[v])); }
        if (lo>.241f || hi<-.241f) return out;
    }
    for (const auto hull : kHeadHulls) {
        std::array<Vec3, 256> storageA, storageB;
        Vec3* polygon=storageA.data(); Vec3* next=storageB.data();
        std::copy(tri.vertices.begin(),tri.vertices.end(),polygon);
        std::size_t count=3;
        for (std::size_t i=hull.start; i<std::size_t(hull.start)+hull.count && count; ++i) {
            const auto& plane=kHeadPlanes[i];
            std::size_t n=0;
            Vec3 a=polygon[count-1];
            float da=dot(plane.normal,a)+plane.distance;
            for (std::size_t j=0; j<count; ++j) {
                const Vec3 b=polygon[j];
                const float db=dot(plane.normal,b)+plane.distance;
                if ((da<=0)!=(db<=0)) {
                    if (n>=storageA.size()) return {};
                    next[n++]=a+(b-a)*(da/(da-db));
                }
                if (db<=0) { if (n>=storageA.size()) return {}; next[n++]=b; }
                a=b; da=db;
            }
            std::swap(polygon,next); count=n;
        }
        if (count) {
            Vec3 point{};
            for (std::size_t i=0; i<count; ++i) point=point+polygon[i];
            out.hit=true; out.pointM=point/static_cast<float>(count); return out;
        }
    }
    return out;
}

struct Quaternion { float w{1},x{},y{},z{}; };
inline Quaternion quaternion(const Mat3& m) {
    Quaternion q{};
    const float trace=m.m[0][0]+m.m[1][1]+m.m[2][2];
    if (trace>0) {
        const float s=std::sqrt(trace+1)*2;
        q={s*.25f,(m.m[2][1]-m.m[1][2])/s,(m.m[0][2]-m.m[2][0])/s,(m.m[1][0]-m.m[0][1])/s};
    } else {
        int i=0; if (m.m[1][1]>m.m[0][0]) i=1; if (m.m[2][2]>m.m[i][i]) i=2;
        const int j=(i+1)%3,k=(i+2)%3;
        const float s=std::sqrt(std::max(0.f,1+m.m[i][i]-m.m[j][j]-m.m[k][k]))*2;
        if (s<1e-6f) return q;
        float v[3]{}; v[i]=s*.25f; v[j]=(m.m[j][i]+m.m[i][j])/s; v[k]=(m.m[k][i]+m.m[i][k])/s;
        q={(m.m[k][j]-m.m[j][k])/s,v[0],v[1],v[2]};
    }
    const float n=std::sqrt(q.w*q.w+q.x*q.x+q.y*q.y+q.z*q.z);
    return {q.w/n,q.x/n,q.y/n,q.z/n};
}
inline float qdot(Quaternion a,Quaternion b) { return a.w*b.w+a.x*b.x+a.y*b.y+a.z*b.z; }
inline float rotationAngle(const Mat3& a,const Mat3& b) {
    return 2*std::acos(std::clamp(std::fabs(qdot(quaternion(a),quaternion(b))),0.f,1.f));
}
inline Mat3 interpolateRotation(const Mat3& a,const Mat3& b,float t) {
    auto qa=quaternion(a),qb=quaternion(b);
    float d=qdot(qa,qb);
    if (d<0) { qb={-qb.w,-qb.x,-qb.y,-qb.z}; d=-d; }
    float wa=1-t,wb=t;
    if (d<.9995f) { const float angle=std::acos(std::clamp(d,0.f,1.f)); wa=std::sin((1-t)*angle)/std::sin(angle); wb=std::sin(t*angle)/std::sin(angle); }
    Quaternion q{wa*qa.w+wb*qb.w,wa*qa.x+wb*qb.x,wa*qa.y+wb*qb.y,wa*qa.z+wb*qb.z};
    const float n=std::sqrt(qdot(q,q)); q={q.w/n,q.x/n,q.y/n,q.z/n};
    const float x=q.x,y=q.y,z=q.z,w=q.w;
    Mat3 r{};
    r.m[0][0]=1-2*(y*y+z*z); r.m[0][1]=2*(x*y-z*w); r.m[0][2]=2*(x*z+y*w);
    r.m[1][0]=2*(x*y+z*w); r.m[1][1]=1-2*(x*x+z*z); r.m[1][2]=2*(y*z-x*w);
    r.m[2][0]=2*(x*z-y*w); r.m[2][1]=2*(y*z+x*w); r.m[2][2]=1-2*(x*x+y*y);
    return r;
}
inline RigidTransform interpolate(const RigidTransform& a,const RigidTransform& b,float t) {
    return {a.translation+(b.translation-a.translation)*t,interpolateRotation(a.rotation,b.rotation,t),a.scale+(b.scale-a.scale)*t};
}
inline Contact intersect(const Triangle& local,const RigidTransform& weapon,const RigidTransform& head) {
    Triangle h{};
    for (std::size_t i=0;i<3;++i) h.vertices[i]=worldToLocalPoint(head,localToWorldPoint(weapon,local.vertices[i]));
    auto c=intersectHeadLocal(h);
    if (c.hit) c.pointM=localToWorldPoint(head,c.pointM);
    return c;
}

// Motion sampling accounts for translation, angular motion and scale of BOTH
// bodies. A positive always includes an exact triangle/convex intersection.
// The 2mm bound limits tunnelling; grazing contacts thinner than that can be
// missed. This is deliberately not labelled exact continuous collision.
inline int sweepSteps(const RigidTransform& weapon0,const RigidTransform& weapon1,
                      const RigidTransform& head0,const RigidTransform& head1,float weaponRadius) {
    if (!valid(weapon0)||!valid(weapon1)||!valid(head0)||!valid(head1)||!std::isfinite(weaponRadius)||weaponRadius<0) return 0;
    const float ws=std::max(weapon0.scale,weapon1.scale),hs=std::max(head0.scale,head1.scale);
    const float movement=length(weapon1.translation-weapon0.translation)+length(head1.translation-head0.translation)+
        rotationAngle(weapon0.rotation,weapon1.rotation)*weaponRadius*ws+
        rotationAngle(head0.rotation,head1.rotation)*.241f*hs+
        std::fabs(weapon1.scale-weapon0.scale)*weaponRadius+std::fabs(head1.scale-head0.scale)*.241f;
    if (!std::isfinite(movement)||movement>1.024f) return 0;
    return std::max(1,static_cast<int>(std::ceil(movement/.002f)));
}
inline Contact sweep(const Triangle& triangle,const RigidTransform& weapon0,const RigidTransform& weapon1,
                     const RigidTransform& head0,const RigidTransform& head1,int steps) {
    if (steps<1||steps>512) return {};
    for (int i=0;i<=steps;++i) {
        const float t=static_cast<float>(i)/static_cast<float>(steps);
        auto result=intersect(triangle,interpolate(weapon0,weapon1,t),interpolate(head0,head1,t));
        if (result.hit) { result.time=t; return result; }
    }
    return {};
}

} // namespace cms::weaponmesh
