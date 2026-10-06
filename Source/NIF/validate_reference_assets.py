"""Independent checks of emitted CMS geometry + glTF before NIF conversion."""
import argparse,json,struct,io
from PIL import Image
from pathlib import Path
import numpy as np
from weapon_dimensions import MODEL_SCALE as S, LINK_COUNT, FIRST_LINK, LINK_SPACING, HEAD_REACH

def validate(build):
    path=build/'visual-preview/reference_mesh.cms';tokens=iter(path.read_text().split())
    def ints(n):return [int(next(tokens)) for _ in range(n)]
    def floats(n):return [float(next(tokens)) for _ in range(n)]
    assert next(tokens)=='CMSMESH' and int(next(tokens))==1
    nn,nm,nh=ints(3);assert nn==LINK_COUNT+3 and nh==15 and nm==LINK_COUNT+13
    nodes=[];meshes=[]
    for i in range(nn):
        name=next(tokens);parent=int(next(tokens));pos=floats(3);rot=np.array(floats(9)).reshape(3,3)
        assert parent<i and np.allclose(rot@rot.T,np.eye(3),atol=1e-6) and np.linalg.det(rot)>.999
        nodes.append((name,parent,pos,rot))
    assert nodes[1][0]=='CMS_ChainAnchor' and np.allclose(nodes[1][2],[0,.4*S,0])
    for i in range(LINK_COUNT):
        assert nodes[i+2][0]==f'CMS_LinkNode_{i:02d}' and nodes[i+2][1]==1
        assert np.allclose(nodes[i+2][2],[0,0,(FIRST_LINK+i*LINK_SPACING)*S])
    assert nodes[LINK_COUNT+2][0]=='CMS_HeadNode' and np.allclose(nodes[LINK_COUNT+2][2],[0,0,HEAD_REACH*S])
    for i in range(nm):
        name=next(tokens);parent,material,nv,nt=ints(4);assert nv<65536 and nt<65536
        data=np.array(floats(8*nv)).reshape(nv,8);f=np.array(ints(3*nt)).reshape(nt,3);assert np.isfinite(data).all()
        assert f.min()>=0 and f.max()<nv
        v=data[:,:3];n=data[:,3:6];assert np.max(abs(np.linalg.norm(n,axis=1)-1))<1e-6
        fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
        assert (np.linalg.norm(fn,axis=1)>1e-12).all(),name+' degenerate triangle'
        assert (np.sum(fn*n[f].mean(1),axis=1)>-1e-10).all(),name+' winding disagrees with normals'
        if 2<=parent<LINK_COUNT+2:
            span=np.ptp(v@nodes[parent][3].T,axis=0)
            assert np.ptp(v,axis=0)[0]>np.ptp(v,axis=0)[1]*3,'Baked alternation would conflict with runtime roll'
            assert span[(parent-2)%2]>span[1-(parent-2)%2]*3,'Chain links not alternating'
            assert np.ptp(data[f,7],axis=1).max()<=.0750001,'Chain closure drags texture backwards across repeat seam'
            assert np.allclose(data[:11,:6],data[-11:,:6],atol=1e-9),'Closed chain geometry seam split'
        meshes.append((name,parent,material,data,f))
    hulls=[];hull_planes=[]
    for i in range(nh):
        nv,np_=ints(2);margin=float(next(tokens));v=np.array(floats(nv*3)).reshape(nv,3);planes=np.array(floats(np_*4)).reshape(np_,4)
        assert np.max(v@planes[:,:3].T+planes[:,3])<1e-7,'Vertex outside hull'
        assert abs(np.max(np.linalg.norm(v,axis=1))-(.16 if i==0 else .24)*S)<1e-6
        assert abs(margin-(.003 if i==0 else .002)*S)<1e-10
        hulls.append(v);hull_planes.append(planes)
    assert next(tokens,None) is None
    # Exact current collision direction contract including empty chain socket axis.
    r=np.sqrt(1-.64**2)
    dirs=[[np.cos(i*np.pi/4+np.pi/8),0,np.sin(i*np.pi/4+np.pi/8)] for i in range(8)]
    dirs.extend([[r*np.cos(i*2*np.pi/3),y,r*np.sin(i*2*np.pi/3)] for y in [-.64,.64] for i in range(3)])
    for d,v in zip(dirs,hulls[1:]):
        assert np.min(np.linalg.norm(v-np.array(d)*.24*S,axis=1))<1e-6,'Wrong spike direction'
    manifest=json.loads((build/'visual-preview/asset_manifest.json').read_text())
    assert manifest['dimensions']['model_scale']==S and manifest['dimensions']['chain_links']==LINK_COUNT
    assert abs(manifest['dimensions']['anchor_to_head_m']-HEAD_REACH*S)<1e-9
    # Independently inspect the emitted curved shell, including texture-space
    # registration and topological closure. No older dragon contour is drawn.
    emblem=manifest['emblem']
    names=['metal','wood','leather','darksteel','edge','cord','bronze','spike','chain','ring','emblem'];parts={}
    assert emblem['surface']=='spherical_radial_image_relief' and emblem['replaces_previous_contour']
    for part in emblem['parts']:
        matches=[m for m in meshes if m[1]==part['parent'] and m[2]==names.index(part['material'])];assert len(matches)==1
        data=matches[0][3];tri=matches[0][4];vs=part['vertex_start'];ve=vs+part['vertex_count'];fs=part['face_start'];fe=fs+part['face_count']
        assert ve<=len(data) and fe<=len(tri)
        local_tri=tri[fs:fe]-vs;assert local_tri.min()>=0 and local_tri.max()<ve-vs
        parts[part['name']]=(data[vs:ve],local_tri)
    assert set(parts)=={'front','back','sides'}
    assert next(p['material'] for p in emblem['parts'] if p['name']=='front')=='emblem'
    front,front_tri=parts['front'];back,back_tri=parts['back'];side,side_tri=parts['sides']
    angle=emblem['crest_rotation_rad']
    rot=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    front_v=front[:,:3]@rot;back_v=back[:,:3]@rot
    front_r=np.linalg.norm(front_v,axis=1);back_r=np.linalg.norm(back_v,axis=1)
    assert front.shape==back.shape and np.allclose(front_v/front_r[:,None],back_v/back_r[:,None],atol=1e-8),'Plaque sides are not radial'
    assert front_r.min()>=emblem['front_base_radius_m']-1e-9
    assert front_r.max()<=emblem['front_base_radius_m']+emblem['maximum_image_relief_m']+1e-9
    assert np.max(abs(back_r-emblem['back_radius_m']))<1e-9 and back_r.max()<.148*S,'Plaque back does not embed into forged sphere'
    # Even triangle interiors clear the maximum 160 mm core sphere. The front
    # mesh is actually curved, not a planar face with a bent border.
    centroid=front_v[front_tri].mean(axis=1)
    edge_mid=(front_v[front_tri]+np.roll(front_v[front_tri],-1,axis=1))*.5
    assert min(np.linalg.norm(centroid,axis=1).min(),np.linalg.norm(edge_mid,axis=2).min())>.160*S,'Curved front intersects sphere between vertices'
    assert np.ptp(front_v[:,1])>.06*S,'Emblem face is still planar'
    projected=front_v*(emblem['sphere_radius_m']/front_r[:,None])
    pixels=np.column_stack([projected[:,0]/emblem['scale_m_per_pixel']+emblem['center_pixel'][0],emblem['center_pixel'][1]-projected[:,2]/emblem['scale_m_per_pixel']])
    size=np.array(emblem['source_dimensions_px'])-1
    uv_px=np.column_stack([front[:,6]*size[0],(1-front[:,7])*size[1]])
    assert np.max(abs(pixels-uv_px))<1e-4,'Emblem source image is offset, stretched, or mirrored'
    assert np.all(front[:,6:8]>=0) and np.all(front[:,6:8]<=1),'Non-tiling emblem repeats outside its image'
    corners=np.asarray(emblem['source_corners_px']);boundary=np.asarray(emblem['boundary_vertex_indices']);nedge=emblem['edge_subdivisions']
    assert len(boundary)==nedge*4
    expected=np.concatenate([corners[i]+(corners[(i+1)%4]-corners[i])*np.arange(nedge)[:,None]/nedge for i in range(4)])
    assert np.max(abs(pixels[boundary]-expected))<1e-4,'Diamond boundary no longer follows source corners'
    u=pixels[front_tri[:,1]]-pixels[front_tri[:,0]];w=pixels[front_tri[:,2]]-pixels[front_tri[:,0]]
    area=np.abs(u[:,0]*w[:,1]-u[:,1]*w[:,0]).sum()/2
    source_area=abs(np.sum(corners[:,0]*np.roll(corners[:,1],-1)-corners[:,1]*np.roll(corners[:,0],-1)))/2
    assert abs(area/source_area-1)<1e-7,'Curved image surface has missing or overlapping triangles'
    # Weld the independently emitted front/back/side vertices geometrically,
    # then require each edge twice with opposite orientation (closed shell).
    all_v=np.vstack([front[:,:3],back[:,:3],side[:,:3]])
    all_f=np.vstack([front_tri,back_tri+len(front),side_tri+len(front)+len(back)])
    _,weld=np.unique(np.round(all_v,8),axis=0,return_inverse=True)
    wf=weld[all_f];edges=np.vstack([wf[:,[0,1]],wf[:,[1,2]],wf[:,[2,0]]])
    keys=np.sort(edges,axis=1);_,inverse,count=np.unique(keys,axis=0,return_inverse=True,return_counts=True)
    assert np.all(count==2),'Curved plaque is not a closed two-manifold shell'
    orientation=np.zeros(len(count),dtype=int);np.add.at(orientation,inverse,np.where(edges[:,0]<edges[:,1],1,-1))
    assert np.all(orientation==0),'Curved plaque has inverted shell triangles'
    # For every front triangle and every spike hull, find a separating hull
    # plane that puts all three triangle vertices outside. Unlike a vertices-
    # only overlap test this also rejects a spike cutting through a triangle.
    spike_clearance=[]
    for planes in hull_planes[1:]:
        signed=front[front_tri,:3]@planes[:,:3].T+planes[:,3]
        separation=signed.min(axis=1).max(axis=1)
        assert separation.min()>.001*S,'A spike hull clips the textured emblem front'
        spike_clearance.append(float(separation.min()))
    print(f'EMBLEM_SPIKE_CLEARANCE_PASS all front triangles separated from14spikehulls by >= {min(spike_clearance)*1000:.3f}mm')
    import hashlib
    texture=build/'textures/weapons/ChainMorningstarVR'/emblem['processed_texture']
    assert hashlib.sha256(texture.read_bytes()).hexdigest()==emblem['processed_texture_sha256'],'Emblem geometry uses different texture input'
    print(f'EMBLEM_CURVE_PASS front_vertices={len(front)} front_triangles={len(front_tri)} radius={front_r.min():.6f}..{front_r.max():.6f}m buried_back={back_r.max():.6f}m depth_sag={np.ptp(front_v[:,1]):.6f}m source_area={area:.2f}px2 closed_shell=true exact_image_uv=true')
    feature_vertices={};feature_data={}
    material_names=names
    for feature in manifest.get('sculpt_features',[]):
        match=[m for m in meshes if m[1]==feature['parent'] and m[2]==material_names.index(feature['material'])]
        assert len(match)==1
        start=feature['vertex_start'];end=start+feature['vertex_count'];assert end<=len(match[0][3])
        feature_data[feature['name']]=match[0][3][start:end]
        feature_vertices[feature['name']]=match[0][3][start:end,:3]
    assert len(feature_vertices)==17,'Missing sculpted surfaces'
    wood=feature_vertices['rough_wood'];r=np.linalg.norm(wood[:,[0,2]],axis=1)
    hand_r=np.mean(r[(wood[:,1]>.15*S)&(wood[:,1]<.20*S)])
    chain_r=np.mean(r[(wood[:,1]>.32*S)&(wood[:,1]<.36*S)])
    assert hand_r>chain_r*1.10,'Handle must thicken towards hand'
    rows=[r[np.isclose(wood[:,1],yy)] for yy in np.unique(wood[:,1])]
    assert np.median([np.ptp(row) for row in rows])>.002*S,'Wood is still a smooth cylinder'
    leather=feature_vertices['compressed_leather'];lr=np.linalg.norm(leather[:,[0,2]],axis=1)
    rows=[lr[np.isclose(leather[:,1],yy)] for yy in np.unique(leather[:,1])]
    assert np.median([np.ptp(row) for row in rows])>.002*S,'Leather must have actual folds/compression'
    core=feature_vertices['hammered_iron_core'];cr=np.linalg.norm(core,axis=1)
    core_data=feature_data['hammered_iron_core']
    for pole_v in [0.,1.]:
        pole=core_data[core_data[:,7]==pole_v]
        assert len(pole)==81,'Core pole UV copies missing'
        assert np.all(pole[:,:3]==pole[0,:3]),'Core pole depends on longitude (degenerate cap risk)'
        assert np.all(pole[:,3:6]==pole[0,3:6]),'Core pole normals vary by wedge'
        assert np.dot(pole[0,:3],pole[0,3:6])>0,'Core pole normal points inward'
    print('CORE_POLES_PASS each pole has one exact position and one shared outward normal')
    assert np.ptp(cr)>.004*S,'Forged iron has no coarse geometric dents'
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
    for i,(base,kind) in enumerate((b,k) for b in ['metal','wood','leather','cord','spike','chain','ring','emblem'] for k in ['d','n']):
        view=doc['bufferViews'][doc['images'][i]['bufferView']]
        embedded=raw[binstart+view['byteOffset']:binstart+view['byteOffset']+view['byteLength']]
        got=np.asarray(Image.open(io.BytesIO(embedded)).convert('RGB'))
        expected=np.asarray(Image.open(texture_dir/f'cms_{base}_{kind}.png').convert('RGB'))[::-1]
        assert np.array_equal(got,expected),'GLB image orientation/normal convention mismatch'
    print('GLB_MATERIAL_PASS V-up UVs + flipped embedded PNGs; normal green unchanged')
    print(f'ASSET_GEOMETRY_PASS nodes={nn} meshes={nm} triangles={sum(len(m[4]) for m in meshes)} hulls={nh}; GLB matches NIF input')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);args=p.parse_args();validate(args.build)
