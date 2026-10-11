// Read-only inspection with the same pinned nifly used by the guarded writer.
#include <NifFile.hpp>
#include <Shaders.hpp>
#include <iomanip>
#include <iostream>
#include <stdexcept>
using namespace nifly;
int main(int argc,char**argv) try {
    if(argc!=2&&(argc!=3||std::string(argv[2])!="--geometry"))throw std::runtime_error("usage: inspect_nif_materials INPUT.nif [--geometry]");
    const bool geometry=argc==3;
    NifFile nif;
    if(nif.Load(argv[1])!=0||nif.HasUnknown())throw std::runtime_error("Invalid or unknown NIF blocks");
    std::cout<<std::setprecision(9)<<"{\"node_count\":"<<nif.GetNodes().size()<<",\"shapes\":[";
    bool first=true;
    for(auto* shape:nif.GetShapes()) {
        if(!first)std::cout<<',';first=false;
        auto* s=dynamic_cast<BSLightingShaderProperty*>(nif.GetShader(shape));
        std::cout<<"{\"name\":"<<std::quoted(shape->name.get())<<",\"block\":"<<nif.GetBlockID(shape);
        if(s){
            std::cout<<",\"shader_block\":"<<nif.GetBlockID(s)<<",\"type\":"<<s->GetShaderType()
                <<",\"flags1\":"<<s->shaderFlags1<<",\"flags2\":"<<s->shaderFlags2
                <<",\"emissive\":["<<s->emissiveColor.x<<','<<s->emissiveColor.y<<','<<s->emissiveColor.z
                <<"],\"emissive_multiple\":"<<s->emissiveMultiple<<",\"specular_strength\":"<<s->specularStrength
                <<",\"glossiness\":"<<s->glossiness<<",\"environment_scale\":"<<s->environmentMapScale
                <<",\"alpha\":"<<s->alpha<<",\"textures\":[";
            for(int i=0;i<9;i++){if(i)std::cout<<',';std::string path;nif.GetTextureSlot(shape,path,i);std::cout<<std::quoted(path);}
            std::cout<<']';
        }
        if(geometry){
            const auto* vertices=nif.GetVertsForShape(shape);
            std::vector<Triangle> triangles;
            if(!vertices||!shape->GetTriangles(triangles))throw std::runtime_error("Missing shape geometry");
            std::cout<<",\"vertices\":[";
            for(size_t i=0;i<vertices->size();i++){if(i)std::cout<<',';const auto& v=(*vertices)[i];std::cout<<'['<<v.x<<','<<v.y<<','<<v.z<<']';}
            std::cout<<"],\"triangles\":[";
            for(size_t i=0;i<triangles.size();i++){if(i)std::cout<<',';const auto& t=triangles[i];std::cout<<'['<<t.p1<<','<<t.p2<<','<<t.p3<<']';}
            std::cout<<']';
        }
        std::cout<<'}';
    }
    std::cout<<"]}\n";
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
