#include "Source/SKSE/WeaponMeshContactCore.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace cms;
using namespace cms::weaponmesh;

Triangle at(Vec3 p,float size=.001f) { return {{{p+Vec3{0,size,0},p+Vec3{0,-size,size},p+Vec3{0,-size,-size}}}}; }
Mat3 rotationY(float a) { Mat3 r; r.m[0][0]=std::cos(a);r.m[0][2]=std::sin(a);r.m[2][0]=-std::sin(a);r.m[2][2]=std::cos(a);return r; }
Mat3 rotationZ(float a) { Mat3 r; r.m[0][0]=std::cos(a);r.m[0][1]=-std::sin(a);r.m[1][0]=std::sin(a);r.m[1][1]=std::cos(a);return r; }
int main() {
    assert(kHeadHulls.size()==15);
    assert(intersectHeadLocal(at({0,0,0})).hit);
    assert(intersectHeadLocal(at({.14f*kModelScale,0,0})).hit);
    assert(!intersectHeadLocal(at({.3f,0,0})).hit);
    // Empty between spikes despite being inside the enclosing head radius.
    assert(!intersectHeadLocal(at({0,.215f*kModelScale,0})).hit);
    assert(!intersectHeadLocal(at({.217f*kModelScale,0,0})).hit);
    const Vec3 spike{.923879533f*.215f*kModelScale,0,.382683432f*.215f*kModelScale};
    assert(intersectHeadLocal(at(spike)).hit);
    // Large triangle crosses the head although all three vertices are outside.
    assert(intersectHeadLocal(Triangle{{Vec3{0,-1,-1},Vec3{0,1,-1},Vec3{0,0,1}}}).hit);
    assert(!intersectHeadLocal(Triangle{{Vec3{0,0,0},Vec3{0,0,0},Vec3{0,0,0}}}).hit);
    assert(!intersectHeadLocal(at({std::numeric_limits<float>::quiet_NaN(),0,0})).hit);
    RigidTransform origin{},a{},b{};
    a.translation={-.4f,0,0};b.translation={.4f,0,0};
    auto tri=at({0,0,0},.02f);
    assert(!intersect(tri,a,origin).hit&&!intersect(tri,b,origin).hit);
    int steps=sweepSteps(a,b,origin,origin,.03f);
    assert(steps>=400&&sweep(tri,a,b,origin,origin,steps).hit);
    // Rotating weapon tip enters the head although endpoints both miss.
    a.translation=b.translation={-1,0,0};a.rotation=rotationZ(-.35f);b.rotation=rotationZ(.35f);
    tri=at({1,0,0});
    assert(!intersect(tri,a,origin).hit&&!intersect(tri,b,origin).hit);
    steps=sweepSteps(a,b,origin,origin,1.01f);
    assert(steps>300&&sweep(tri,a,b,origin,origin,steps).hit);
    // Native head rotation must be sampled as well as weapon motion.
    a={};b={};b.rotation=rotationY(.785398163f);
    tri=at({.219f*kModelScale,0,0});
    assert(!intersect(tri,origin,a).hit&&!intersect(tri,origin,b).hit);
    steps=sweepSteps(origin,origin,a,b,.22f);
    assert(sweep(tri,origin,origin,a,b,steps).hit);
    // Teleports and invalid transforms fail closed, without increasing step cap.
    b.translation={100,0,0}; assert(sweepSteps(a,b,origin,origin,1)==0);
    b={};b.scale=0;assert(sweepSteps(a,b,origin,origin,1)==0);
    assert(!sweep(tri,origin,origin,origin,origin,513).hit);
    // Quaternion interpolation preserves proper orientation even near pi.
    const auto q=interpolateRotation(Mat3{},rotationZ(3.14159f),.5f);
    assert(approximatelyOrthonormal(q,.0001f));
    assert(std::fabs(mul(q,Vec3{1,0,0}).x)<.0001f);
    // World transforms plus actor scale are applied once, not twice.
    a={};a.scale=2;a.translation={11,15,-3};b=a;
    assert(intersect(at({.14f*kModelScale,0,0}),a,b).hit);
    assert(!intersect(at({.3f,0,0}),a,b).hit);
    std::cout<<"WEAPON_MESH_CONTACT_PASS exact hulls, empty-space rejection, moving triangles, head/weapon rotations, lifecycle input bounds\n";
}
