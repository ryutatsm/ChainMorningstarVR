"""Independent checks of emitted CMS geometry + glTF before NIF conversion."""
import argparse,json,struct,io
from PIL import Image
from pathlib import Path
import numpy as np

def validate(build):
    path=build/'visual-preview/reference_mesh.cms';tokens=iter(path.read_text().split())
    def ints(n):return [int(next(tokens)) for _ in range(n)]
    def floats(n):return [float(next(tokens)) for _ in range(n)]
    assert next(tokens)=='CMSMESH' and int(next(tokens))==1
    nn,nm,nh=ints(3);assert nn==17 and nh==15
    nodes=[];meshes=[]
    for i in range(nn):
        name=next(tokens);parent=int(next(tokens));pos=floats(3);rot=np.array(floats(9)).reshape(3,3)
        assert parent<i and np.allclose(rot@rot.T,np.eye(3),atol=1e-6) and np.linalg.det(rot)>.999
        nodes.append((name,parent,pos,rot))
    assert nodes[1][0]=='CMS_ChainAnchor' and np.allclose(nodes[1][2],[0,.4,0])
    for i in range(14):
        assert nodes[i+2][0]==f'CMS_LinkNode_{i:02d}' and nodes[i+2][1]==1
        assert np.allclose(nodes[i+2][2],[0,0,.035+i*.84/13])
    assert nodes[16][0]=='CMS_HeadNode' and np.allclose(nodes[16][2],[0,0,1.065])
    for i in range(nm):
        name=next(tokens);parent,material,nv,nt=ints(4);assert nv<65536 and nt<65536
        data=np.array(floats(8*nv)).reshape(nv,8);f=np.array(ints(3*nt)).reshape(nt,3);assert np.isfinite(data).all()
        assert f.min()>=0 and f.max()<nv
        v=data[:,:3];n=data[:,3:6];assert np.max(abs(np.linalg.norm(n,axis=1)-1))<1e-6
        fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
        assert (np.linalg.norm(fn,axis=1)>1e-12).all(),name+' degenerate triangle'
        assert (np.sum(fn*n[f].mean(1),axis=1)>-1e-10).all(),name+' winding disagrees with normals'
        if 2<=parent<=15:
            span=np.ptp(v@nodes[parent][3].T,axis=0)
            assert np.ptp(v,axis=0)[0]>np.ptp(v,axis=0)[1]*3,'Baked alternation would conflict with runtime roll'
            assert span[(parent-2)%2]>span[1-(parent-2)%2]*3,'Chain links not alternating'
        meshes.append((name,parent,material,data,f))
    hulls=[];hull_planes=[]
    for i in range(nh):
        nv,np_=ints(2);margin=float(next(tokens));v=np.array(floats(nv*3)).reshape(nv,3);planes=np.array(floats(np_*4)).reshape(np_,4)
        assert np.max(v@planes[:,:3].T+planes[:,3])<1e-7,'Vertex outside hull'
        assert abs(np.max(np.linalg.norm(v,axis=1))-(.16 if i==0 else .24))<1e-6
        assert margin==(.003 if i==0 else .002)
        hulls.append(v);hull_planes.append(planes)
    assert next(tokens,None) is None
    # Exact current collision direction contract including empty chain socket axis.
    r=np.sqrt(1-.64**2)
    dirs=[[np.cos(i*np.pi/4+np.pi/8),0,np.sin(i*np.pi/4+np.pi/8)] for i in range(8)]
    dirs.extend([[r*np.cos(i*2*np.pi/3),y,r*np.sin(i*2*np.pi/3)] for y in [-.64,.64] for i in range(3)])
    for d,v in zip(dirs,hulls[1:]):
        assert np.min(np.linalg.norm(v-np.array(d)*.24,axis=1))<1e-6,'Wrong spike direction'
    manifest=json.loads((build/'visual-preview/asset_manifest.json').read_text())
    feature_vertices={};feature_data={}
    material_names=['metal','wood','leather','darksteel','edge','cord','bronze']
    for feature in manifest.get('sculpt_features',[]):
        match=[m for m in meshes if m[1]==feature['parent'] and m[2]==material_names.index(feature['material'])]
        assert len(match)==1
        start=feature['vertex_start'];end=start+feature['vertex_count'];assert end<=len(match[0][3])
        feature_data[feature['name']]=match[0][3][start:end]
        feature_vertices[feature['name']]=match[0][3][start:end,:3]
    assert len(feature_vertices)==17,'Missing sculpted surfaces'
    wood=feature_vertices['rough_wood'];r=np.linalg.norm(wood[:,[0,2]],axis=1)
    hand_r=np.mean(r[(wood[:,1]>.15)&(wood[:,1]<.20)])
    chain_r=np.mean(r[(wood[:,1]>.32)&(wood[:,1]<.36)])
    assert hand_r>chain_r*1.10,'Handle must thicken towards hand'
    rows=[r[np.isclose(wood[:,1],yy)] for yy in np.unique(wood[:,1])]
    assert np.median([np.ptp(row) for row in rows])>.002,'Wood is still a smooth cylinder'
    leather=feature_vertices['compressed_leather'];lr=np.linalg.norm(leather[:,[0,2]],axis=1)
    rows=[lr[np.isclose(leather[:,1],yy)] for yy in np.unique(leather[:,1])]
    assert np.median([np.ptp(row) for row in rows])>.002,'Leather must have actual folds/compression'
    core=feature_vertices['hammered_iron_core'];cr=np.linalg.norm(core,axis=1)
    core_data=feature_data['hammered_iron_core']
    for pole_v in [0.,1.]:
        pole=core_data[core_data[:,7]==pole_v]
        assert len(pole)==81,'Core pole UV copies missing'
        assert np.all(pole[:,:3]==pole[0,:3]),'Core pole depends on longitude (degenerate cap risk)'
        assert np.all(pole[:,3:6]==pole[0,3:6]),'Core pole normals vary by wedge'
        assert np.dot(pole[0,:3],pole[0,3:6])>0,'Core pole normal points inward'
    print('CORE_POLES_PASS each pole has one exact position and one shared outward normal')
    assert np.ptp(cr)>.004,'Forged iron has no coarse geometric dents'
    planes=hull_planes[0];assert np.max(core@planes[:,:3].T+planes[:,3])<1e-7
    for i in range(14):
        v=feature_vertices[f'battered_spike_{i:02d}'];core_planes=hull_planes[0];spike_planes=hull_planes[i+1]
        inside_core=np.max(v@core_planes[:,:3].T+core_planes[:,3],axis=1)<=1e-7
        inside_spike=np.max(v@spike_planes[:,:3].T+spike_planes[:,3],axis=1)<=1e-7
        assert np.all(inside_core|inside_spike),f'Spike {i} exceeds existing collision hulls'
    print(f'SCULPT_PASS wood_hand_radius={hand_r:.5f}m wood_chain_radius={chain_r:.5f}m core_radius_range={cr.min():.5f}..{cr.max():.5f}m; spikes_inside_collision=true')
    raw=(build/'visual-preview/ChainMorningstar_reference.glb').read_bytes();magic,version,length=struct.unpack_from('<4sII',raw)
    assert magic==b'glTF' and version==2 and length==len(raw)
    length,typ=struct.unpack_from('<I4s',raw,12);assert typ==b'JSON';doc=json.loads(raw[20:20+length]);binstart=20+length+8
    assert len(doc['meshes'])==nm
    for gm,(_,_,_,data,f) in zip(doc['meshes'],meshes):
        prim=gm['primitives'][0]
        for semantic,cols in [('POSITION',slice(0,3)),('NORMAL',slice(3,6)),('TEXCOORD_0',slice(6,8))]:
            acc=doc['accessors'][prim['attributes'][semantic]];view=doc['bufferViews'][acc['bufferView']]
            arr=np.frombuffer(raw,dtype='<f4',offset=binstart+view['byteOffset'],count=data[:,cols].size).reshape(data[:,cols].shape)
            assert np.allclose(arr,data[:,cols],atol=1e-6),'GLB mesh differs from NIF input'
    texture_dir=build/'textures/weapons/ChainMorningstarVR'
    for i,(base,kind) in enumerate((b,k) for b in ['metal','wood','leather'] for k in ['d','n']):
        view=doc['bufferViews'][doc['images'][i]['bufferView']]
        embedded=raw[binstart+view['byteOffset']:binstart+view['byteOffset']+view['byteLength']]
        got=np.asarray(Image.open(io.BytesIO(embedded)).convert('RGB'))
        expected=np.asarray(Image.open(texture_dir/f'cms_{base}_{kind}.png').convert('RGB'))[::-1]
        assert np.array_equal(got,expected),'GLB image orientation/normal convention mismatch'
    print('GLB_MATERIAL_PASS V-up UVs + flipped embedded PNGs; normal green unchanged')
    print(f'ASSET_GEOMETRY_PASS nodes={nn} meshes={nm} triangles={sum(len(m[4]) for m in meshes)} hulls={nh}; GLB matches NIF input')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);args=p.parse_args();validate(args.build)
