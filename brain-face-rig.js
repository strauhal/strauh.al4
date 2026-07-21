(function(){
  "use strict";
  if(!window.THREE) return;

  function damp(a,b,s,dt){ return a+(b-a)*(1-Math.exp(-s*dt)); }
  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
  function PerformanceFace(container,status){
    this.container=container; this.status=status; this.ready=false; this.visible=false;this.active=false;
    this.speaking=false; this.level=0; this.levelTarget=0; this.wordEnergy=0;this.speechEnvelope=0;this.motionEnergy=0;
    this.wordEnvelope=0;this.wordUntil=-1;this.wordShape={jaw:.35,wide:.08,round:.08,cheek:.08,brow:.04,smile:.07};this.mouthAperture=0;
    this.viseme={jaw:0,wide:0,round:0,smile:0,cheek:0,brow:0};
    this.target={jaw:0,wide:0,round:0,smile:0,cheek:0,brow:0};
    this.clock=new THREE.Clock(); this.nextBlink=2.4+Math.random()*2.8;
    this.blinkStart=-10; this.blinkDuration=.14; this.doubleBlink=false;
    this.gestureUntil=0; this.nodKick=0; this.tiltKick=0; this.shrugKick=0;
    this.audioContext=null; this.analyser=null; this.audioData=null;
    this.phase="hidden";this.transitionStart=0;this.presentStart=0;this.assembly=0;this.motionBlend=0;
    this.creepClock=0;
    this.pointer={x:0,y:0,lastMove:-10000};this.lookBlend=0;this.lookUntil=0;this.nextLook=1.2+Math.random()*2.2;
    this.manualDrag=false;this.manualOrbitActive=false;this.graphCameraBusy=false;this.dragPointerId=null;this.dragX=0;this.dragY=0;
    this.graphView=null;this.baseRoot=null;this.baseCamera=null;
    this.manualZoomActive=false;this.manualSyncRatio=1;this.postSpeechHold=false;this.lastAppliedZoom=1;this.previousGraphCameraBusy=false;this.frameDt=.016;
    this.transitionGesture={};this.lastGestureIndex=-1;
    this.topicSurfaces=[];this.detailSurfaces=[];this.assemblySets=[];this.wireLineSets=[];this.fractureSets=[];
    this.responseCount=0;this.detailLevels=[0,0,0,0,0];this.detailTargets=[0,0,0,0,0];
    this.topics=[
      {name:"art",color:0xff5f3d,words:/\b(art|artist|artwork|drawing|painting|design|aesthetic|image|images|portrait|sculpture|color|visual)\b/i},
      {name:"film",color:0xffb000,words:/\b(film|films|cinema|cinematic|video|camera|screen|movie|movies|documentary|footage|portraiture)\b/i},
      {name:"technology",color:0x2f7cff,words:/\b(technology|computer|computers|code|coding|software|internet|digital|algorithm|machine|model|models|data|website|browser|ai|artificial intelligence)\b/i},
      {name:"philosophy",color:0xa94cff,words:/\b(philosophy|meaning|desire|identity|self|psychoanalysis|lacan|freud|god|death|existence|ethics|consciousness)\b/i},
      {name:"memory",color:0xff3f89,words:/\b(memory|memories|archive|archives|history|historical|past|remember|remembering|time|nostalgia|diary)\b/i},
      {name:"body",color:0xff835f,words:/\b(body|face|brain|mind|head|skin|eyes|mouth|voice|breath|breathing|embodiment|physical|human)\b/i},
      {name:"society",color:0x20c6b0,words:/\b(society|social|culture|cultural|politics|political|capital|labor|community|atomization|public|collective)\b/i},
      {name:"space",color:0x72d447,words:/\b(space|spatial|architecture|architectural|place|city|environment|landscape|room|home|geography)\b/i}
    ];
    this.topicLevels=this.topics.map(function(){return 0;});
    this.topicTargets=this.topics.map(function(){return 0;});

    this.renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:"high-performance"});
    // Render at the display's native density. The former 1x backing buffer was
    // enlarged by Retina browsers and made otherwise one-pixel lines fuzzy.
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
    this.renderer.outputEncoding=THREE.sRGBEncoding;
    this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure=.82;
    this.renderer.physicallyCorrectLights=true;
    this.renderer.domElement.setAttribute("aria-label","Interactive rigged 3D portrait of Ernest");
    this.renderer.domElement.style.touchAction="none";
    container.appendChild(this.renderer.domElement);

    this.scene=new THREE.Scene();
    this.camera=new THREE.PerspectiveCamera(22,1,.01,20);
    this.camera.position.set(0,.50,1.85);
    this.controls=new THREE.OrbitControls(this.camera,this.renderer.domElement);
    this.controls.enableDamping=true; this.controls.dampingFactor=.07;
    // The graph is the sole camera operator; local drag/scroll must not fight
    // the synchronized rail movement.
    this.controls.enableRotate=false;this.controls.enableZoom=false;this.controls.enablePan=false;
    // Camera distance is authored by the shared graph zoom. OrbitControls still
    // updates orientation matrices each frame, so its old .75–3.0 limits were
    // silently re-clamping the face after synchronization and making the two
    // layers scale at visibly different rates.
    this.controls.minDistance=.0001; this.controls.maxDistance=1000000;
    this.controls.minPolarAngle=.72; this.controls.maxPolarAngle=2.1;
    this.controls.target.set(0,.49,0);

    var hemi=new THREE.HemisphereLight(0xffeee4,0x16233f,1.7); this.scene.add(hemi);
    var key=new THREE.DirectionalLight(0xffe4d2,2.15); key.position.set(-1.5,2.2,2.4); this.scene.add(key);
    var fill=new THREE.DirectionalLight(0xb9cbff,.78); fill.position.set(1.8,.7,1.4); this.scene.add(fill);
    var rim=new THREE.DirectionalLight(0x9eb4ff,.55); rim.position.set(0,1,-2); this.scene.add(rim);
    this.resize=this.resize.bind(this); window.addEventListener("resize",this.resize); this.resize();
    var self=this;
    window.addEventListener("pointermove",function(e){
      self.pointer.x=clamp(e.clientX/(innerWidth||1)*2-1,-1,1);
      self.pointer.y=clamp(e.clientY/(innerHeight||1)*2-1,-1,1);
      self.pointer.lastMove=performance.now();
    },{passive:true});
    // The portrait occupies the interactive layer while visible. Feed its drag
    // delta into the graph's camera instead of running a second independent
    // orbit controller; the existing graph-to-face synchronization then moves
    // both worlds by precisely the same amount.
    this.renderer.domElement.addEventListener("pointerdown",function(e){
      if(!self.visible||self.speaking||self.graphCameraBusy||e.button!==0)return;
      self.manualDrag=true;self.manualOrbitActive=true;self.dragPointerId=e.pointerId;
      self.dragX=e.clientX;self.dragY=e.clientY;
      self.renderer.domElement.style.cursor="grabbing";
      if(self.renderer.domElement.setPointerCapture)self.renderer.domElement.setPointerCapture(e.pointerId);
      if(window.__brainFaceGraphDrag)window.__brainFaceGraphDrag("start",0,0);
      e.preventDefault();e.stopPropagation();
    });
    this.renderer.domElement.addEventListener("pointermove",function(e){
      if(!self.manualDrag||e.pointerId!==self.dragPointerId)return;
      var dx=e.clientX-self.dragX,dy=e.clientY-self.dragY;self.dragX=e.clientX;self.dragY=e.clientY;
      if(window.__brainFaceGraphDrag)window.__brainFaceGraphDrag("move",dx,dy);
      e.preventDefault();e.stopPropagation();
    });
    function finishManualDrag(e){
      if(!self.manualDrag||(e&&e.pointerId!==self.dragPointerId))return;
      self.manualDrag=false;self.dragPointerId=null;self.renderer.domElement.style.cursor="grab";
      if(window.__brainFaceGraphDrag)window.__brainFaceGraphDrag("end",0,0);
      if(e){e.preventDefault();e.stopPropagation();}
    }
    this.renderer.domElement.addEventListener("pointerup",finishManualDrag);
    this.renderer.domElement.addEventListener("pointercancel",finishManualDrag);
    this.renderer.domElement.addEventListener("wheel",function(e){
      if(!self.visible||self.speaking||self.graphCameraBusy)return;
      self.manualOrbitActive=true;
      if(window.__brainFaceGraphZoom)window.__brainFaceGraphZoom(e.deltaY,e.clientX,e.clientY);
      e.preventDefault();e.stopPropagation();
    },{passive:false});
    this.frame=this.frame.bind(this); requestAnimationFrame(this.frame);
  }

  PerformanceFace.prototype.resize=function(){
    var w=this.container.clientWidth||innerWidth,h=this.container.clientHeight||innerHeight;
    this.renderer.setSize(w,h,false); this.camera.aspect=w/h; this.camera.updateProjectionMatrix();
  };
  PerformanceFace.prototype.load=function(url){
    var self=this;
    if(this.status){this.status.textContent="loading performance rig…";this.status.classList.add("on");}
    new THREE.GLTFLoader().load(url,function(gltf){
      self.root=gltf.scene; self.scene.add(self.root);
      self.nodes={}; self.morphMeshes=[];
      self.topicSurfaces=[];self.detailSurfaces=[];self.assemblySets=[];self.wireLineSets=[];self.fractureSets=[];
      self.root.traverse(function(o){
        self.nodes[o.name]=o;
        if(o.isMesh){
          o.frustumCulled=false;
          if(o.morphTargetDictionary) self.morphMeshes.push(o);
          if(o.name==="TeethUpper"){o.visible=false;return;}
          var aperture=o.name==="MouthCavity";
          var likeness=o.name==="Ernest_Likeness_Detail";
          var black=new THREE.MeshBasicMaterial({color:0x000000,wireframe:!aperture,wireframeLinewidth:1,side:THREE.FrontSide});
          black.skinning=!!o.isSkinnedMesh;black.morphTargets=!!o.morphTargetDictionary;
          if(aperture){
            o.material=black;
          }else if(likeness){
            self.installDetailSurface(o);
          }else{
            self.installTopicSurface(o);
          }
        }
      });
      self.bones={};
      ["Root","Chest","Neck","Head","Shoulder_L","Shoulder_R","Jaw"].forEach(function(n){
        var b=self.nodes[n]; if(b){ self.bones[n]=b; b.userData.basePos=b.position.clone(); b.userData.baseRot=b.rotation.clone(); }
      });
      self.lids=[self.nodes.BlinkUpper_L,self.nodes.BlinkLower_L,self.nodes.BlinkUpper_R,self.nodes.BlinkLower_R].filter(Boolean);
      self.lids.forEach(function(o){o.userData.baseScale=o.scale.clone();});
      self.mouthCavity=self.nodes.MouthCavity;self.teeth=self.nodes.TeethUpper;
      if(self.mouthCavity)self.mouthCavity.userData.baseScale=self.mouthCavity.scale.clone();
      if(self.teeth)self.teeth.userData.baseScale=self.teeth.scale.clone();
      self.irises=[self.nodes.Iris_L,self.nodes.Pupil_L,self.nodes.Catchlight_L,self.nodes.Iris_R,self.nodes.Pupil_R,self.nodes.Catchlight_R].filter(Boolean);
      self.irises.forEach(function(o){o.userData.basePos=o.position.clone();});
      self.fit(); self.ready=true;
      if(self.visible){self.phase="entering";self.transitionStart=self.clock.elapsedTime;self.active=true;self.reshuffleAssembly();}
      if(self.status)self.status.classList.remove("on");
      self.container.dispatchEvent(new CustomEvent("rigready"));
    },undefined,function(err){
      console.error("performance rig",err); if(self.status){self.status.textContent="could not load performance rig";self.status.classList.add("on");}
      self.container.dispatchEvent(new CustomEvent("rigerror"));
    });
  };
  PerformanceFace.prototype.fit=function(){
    var box=new THREE.Box3().setFromObject(this.root),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());
    this.baseRoot={position:this.root.position.clone(),rotation:this.root.rotation.clone(),scale:this.root.scale.clone()};
    this.controls.target.copy(center); this.controls.target.y+=size.y*.05;
    var fov=THREE.MathUtils.degToRad(this.camera.fov),dist=(size.y*.58)/Math.tan(fov/2);
    this.camera.position.set(center.x,center.y+size.y*.03,center.z+dist*1.05);
    this.camera.near=Math.max(.01,dist/100);this.camera.far=dist*12;this.camera.updateProjectionMatrix();this.controls.update();
    var offset=this.camera.position.clone().sub(this.controls.target),spherical=new THREE.Spherical().setFromVector3(offset);
    this.baseCamera={target:this.controls.target.clone(),radius:spherical.radius,phi:spherical.phi,theta:spherical.theta};
  };
  PerformanceFace.prototype.setGraphView=function(k,fitK,tx,ty,yaw,pitch,w,h,cx,cy,busy){
    this.graphView={k:k,fitK:fitK,tx:tx,ty:ty,yaw:yaw,pitch:pitch,w:w||innerWidth,h:h||innerHeight,cx:cx,cy:cy};
    this.graphCameraBusy=!!busy;
    this.previousGraphCameraBusy=this.graphCameraBusy;
  };
  PerformanceFace.prototype.applyManualGraphZoom=function(graphZoom){
    if(this.speaking||this.graphCameraBusy||!isFinite(graphZoom)||graphZoom<=0)return;
    if(this.postSpeechHold){
      this.postSpeechHold=false;
      this.manualZoomActive=true;
      this.manualSyncRatio=(this.lastAppliedZoom||1)/Math.max(.0001,graphZoom);
    }else if(!this.manualZoomActive){
      this.manualZoomActive=true;
      this.manualSyncRatio=(this.lastAppliedZoom||1)/Math.max(.0001,graphZoom);
    }
  };
  PerformanceFace.prototype.applyGraphView=function(){
    if(!this.root||!this.baseRoot||!this.baseCamera||!this.graphView)return;
    var g=this.graphView,b=this.baseRoot,c=this.baseCamera;
    // Use the graph's absolute camera state, not the state at the moment Face
    // was opened. This lets the hidden portrait continuously remember every
    // orbit, pan and zoom made before it is revealed.
    var dx=((g.cx==null?g.w*.5:g.cx)-g.w*.5)/(g.w||1),dy=((g.cy==null?g.h*.5:g.cy)-g.h*.5)/(g.h||1);
    // Match the graph's scale ratio directly so one wheel step has nearly the
    // same apparent magnification in both renderers. Clamp only at the bust's
    // practical near/far limits to avoid camera clipping.
    var graphZoom=g.k/Math.max(.0001,g.fitK);
    // Node flights legitimately magnify the enormous brain graph by several
    // times, but applying that ratio literally to a compact portrait produces
    // an eye-and-nose crop. Preserve one-to-one response through the fitted
    // view, then compress only the close range into a head-and-shoulders shot.
    var framedZoom=graphZoom<=1?clamp(graphZoom,.45,1):1+Math.log(graphZoom)*.12;
    framedZoom=clamp(framedZoom,.45,1.22);
    // Manual wheel input supplies the graph's actual post-clamp scale ratio.
    // Applying that value directly keeps both renderers at precisely the same
    // enlargement rate, independent of camera framing or update order.
    var manualFraming=this.manualZoomActive&&!this.speaking&&!this.postSpeechHold;
    if(manualFraming)this.manualSyncRatio=damp(this.manualSyncRatio,1,10,this.frameDt||.016);
    var zoom=manualFraming?graphZoom*this.manualSyncRatio:framedZoom;
    zoom=clamp(zoom,.02,400);
    this.lastAppliedZoom=zoom;
    // Keep the bust fixed in space. Graph movement drives a real camera orbit
    // around it, like a camera dolly on a circular rail, rather than dragging
    // the rendered portrait across the browser window.
    this.root.position.copy(b.position);this.root.rotation.copy(b.rotation);this.root.scale.copy(b.scale);
    var azimuth=c.theta+g.yaw*.55+clamp(dx,-1,1)*.72;
    var elevation=clamp(c.phi+g.pitch*.42+clamp(dy,-1,1)*.34,.62,2.18);
    var orbit=new THREE.Spherical(c.radius,elevation,azimuth),offset=new THREE.Vector3().setFromSpherical(orbit);
    this.controls.target.copy(c.target);
    this.camera.position.copy(c.target).add(offset);
    this.camera.lookAt(c.target);
    // Projection zoom is uniform across every depth and never pushes the camera
    // through the mesh, so it can follow the graph's full deep-zoom range.
    this.camera.zoom=zoom;
    this.camera.near=Math.max(.001,c.radius/1000);
    this.camera.far=c.radius*12;
    this.camera.updateProjectionMatrix();
  };
  PerformanceFace.prototype.renderGraphFrame=function(){
    if(!this.ready||!this.active)return;
    this.applyGraphView();
    this.controls.update();
    this.renderer.render(this.scene,this.camera);
  };
  PerformanceFace.prototype.setMorph=function(name,value){
    this.morphMeshes.forEach(function(m){var i=m.morphTargetDictionary[name];if(i!==undefined)m.morphTargetInfluences[i]=value;});
  };
  PerformanceFace.prototype.installTopicSurface=function(mesh){
    var geometry=mesh.geometry,pos=geometry&&geometry.attributes.position;if(!pos)return;
    var source=geometry.index?geometry.index.array:null,indices=[],i;
    if(source)for(i=0;i<source.length;i++)indices.push(source[i]);
    else for(i=0;i<pos.count;i++)indices.push(i);
    var bounds=new THREE.Box3().setFromBufferAttribute(pos),size=bounds.getSize(new THREE.Vector3());
    var center=bounds.getCenter(new THREE.Vector3()),zones=this.topics.map(function(){return [];});
    for(i=0;i<indices.length;i+=3){
      var a=indices[i],b=indices[i+1],c=indices[i+2];
      var x=((pos.getX(a)+pos.getX(b)+pos.getX(c))/3-center.x)/(size.x||1);
      var y=((pos.getY(a)+pos.getY(b)+pos.getY(c))/3-center.y)/(size.y||1);
      var z=((pos.getZ(a)+pos.getZ(b)+pos.getZ(c))/3-center.z)/(size.z||1);
      // Two low-frequency spatial waves create broad interlocking regions,
      // avoiding the tiny triangle-by-triangle "scale" pattern.
      var field=Math.sin(x*5.2+y*3.1+z*2.3)+Math.sin(y*6.1-z*3.7+x*1.9);
      var zone=Math.max(0,Math.min(this.topics.length-1,Math.floor((field+2)*.25*this.topics.length)));
      zones[zone].push(a,b,c);
    }
    var reordered=[],materials=[],self=this;
    geometry.clearGroups();
    zones.forEach(function(zone,topicIndex){
      var start=reordered.length;Array.prototype.push.apply(reordered,zone);
      var mat=new THREE.MeshStandardMaterial({
        color:self.topics[topicIndex].color,roughness:.9,metalness:0,
        emissive:self.topics[topicIndex].color,emissiveIntensity:.08,
        transparent:true,opacity:0,flatShading:true,side:THREE.FrontSide,
        depthWrite:false,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1
      });
      mat.skinning=!!mesh.isSkinnedMesh;mat.morphTargets=!!mesh.morphTargetDictionary;
      materials.push(mat);geometry.addGroup(start,zone.length,topicIndex);
      var hsl={h:0,s:0,l:0};mat.color.getHSL(hsl);
      self.topicSurfaces.push({material:mat,topic:topicIndex,h:hsl.h,s:hsl.s,l:hsl.l,phase:topicIndex*.83+Math.random()*1.7});
    });
    var IndexType=pos.count>65535?Uint32Array:Uint16Array;
    geometry.setIndex(new THREE.BufferAttribute(new IndexType(reordered),1));
    mesh.material=materials;
    // Build a separate edge network so construction order is independent of
    // the scan's spatially sorted triangle/index order.
    var seen={},edgeGroups=[[],[]];
    for(i=0;i<indices.length;i+=3){
      var tri=[indices[i],indices[i+1],indices[i+2]];
      for(var e=0;e<3;e++){
        var ea=tri[e],eb=tri[(e+1)%3],lo=Math.min(ea,eb),hi=Math.max(ea,eb),key=lo+":"+hi;
        if(!seen[key]){
          seen[key]=1;
          var edgeX=(pos.getX(ea)+pos.getX(eb))*.5,edgeY=(pos.getY(ea)+pos.getY(eb))*.5,edgeZ=(pos.getZ(ea)+pos.getZ(eb))*.5;
          var facial=edgeY<-.045&&edgeZ>.40&&edgeZ<.68&&Math.abs(edgeX)<.44;
          edgeGroups[facial?1:0].push(ea,eb);
        }
      }
    }
    mesh.renderOrder=1;
    edgeGroups.forEach(function(edges,facial){
      if(!edges.length)return;
      var lineGeometry=new THREE.BufferGeometry();
      lineGeometry.setAttribute("position",new THREE.BufferAttribute(new Float32Array(edges.length*3),3));
      var lines=new THREE.LineSegments(lineGeometry,new THREE.LineBasicMaterial({color:0x000000,linewidth:1,transparent:true,opacity:1,depthWrite:false}));
      lines.frustumCulled=false;lines.renderOrder=2;mesh.add(lines);
      self.wireLineSets.push({mesh:mesh,lines:lines,indices:edges,facial:!!facial,tmpA:new THREE.Vector3(),tmpB:new THREE.Vector3()});
    });

    // Find the actual outer hull in all three principal projections. Sampling
    // by vertex order biased the old fray toward the scalp; angular hull bins
    // distribute equally around head, ears, neck, shoulders and lower torso.
    var fractureIndices=[],directions=[],jitters=[],lengths=[],hull={};
    function keepHull(key,index,score){var old=hull[key];if(!old||score>old.score)hull[key]={index:index,score:score};}
    var sectors=84;
    for(i=0;i<pos.count;i++){
      var fx=(pos.getX(i)-center.x)/(size.x||1),fy=(pos.getY(i)-center.y)/(size.y||1),fz=(pos.getZ(i)-center.z)/(size.z||1);
      [[fx,fz,"xz"],[fx,fy,"xy"],[fy,fz,"yz"]].forEach(function(plane){
        var angle=Math.atan2(plane[1],plane[0]),sector=Math.floor((angle+Math.PI)/(Math.PI*2)*sectors)%sectors;
        keepHull(plane[2]+sector,i,Math.hypot(plane[0],plane[1]));
      });
    }
    var used={};Object.keys(hull).forEach(function(key){
      var index=hull[key].index;if(used[index])return;used[index]=1;
      var fx=(pos.getX(index)-center.x)/(size.x||1),fy=(pos.getY(index)-center.y)/(size.y||1),fz=(pos.getZ(index)-center.z)/(size.z||1);
      var baseDir=new THREE.Vector3(fx*1.25,fy*.38,fz*1.25);if(baseDir.lengthSq()<.0001)baseDir.set(1,0,0);baseDir.normalize();
      var tangent=new THREE.Vector3(-baseDir.z,.34*Math.sin(index*2.17),baseDir.x).normalize();
      // Two independently animated threads leave every sampled hull vertex.
      // Their small fan makes the silhouette read as torn woven canvas rather
      // than a halo of isolated hairs or dots.
      for(var strand=0;strand<2;strand++){
        var fan=strand===0?-.18:.18;
        var dir=baseDir.clone().addScaledVector(tangent,fan).normalize();
        var jitter=tangent.clone().multiplyScalar(strand===0?-1:1);
        fractureIndices.push(index);directions.push(dir);jitters.push(jitter);
        lengths.push(.050+.145*((Math.sin(index*91.17+strand*7.31)*.5+.5)));
      }
    });
    var fractureGeometry=new THREE.BufferGeometry(),fracturePositions=new Float32Array(fractureIndices.length*18),fractureColors=new Float32Array(fractureIndices.length*18);
    for(i=0;i<fractureIndices.length;i++){
      var cp=i*18;
      for(var fv=0;fv<6;fv++){
        var shade=0;
        fractureColors[cp+fv*3]=shade;fractureColors[cp+fv*3+1]=shade;fractureColors[cp+fv*3+2]=shade;
      }
    }
    fractureGeometry.setAttribute("position",new THREE.BufferAttribute(fracturePositions,3));
    fractureGeometry.setAttribute("color",new THREE.BufferAttribute(fractureColors,3));
    var fractureLines=new THREE.LineSegments(fractureGeometry,new THREE.LineBasicMaterial({vertexColors:true,linewidth:1,transparent:true,opacity:.94,depthWrite:false}));
    fractureLines.frustumCulled=false;fractureLines.renderOrder=2;mesh.add(fractureLines);
    this.fractureSets.push({mesh:mesh,lines:fractureLines,indices:fractureIndices,directions:directions,jitters:jitters,lengths:lengths,tmp:new THREE.Vector3()});
  };
  PerformanceFace.prototype.installDetailSurface=function(mesh){
    var geometry=mesh.geometry,pos=geometry&&geometry.attributes.position;if(!pos)return;
    var source=geometry.index?geometry.index.array:null,indices=[],i;
    if(source)for(i=0;i<source.length;i++)indices.push(source[i]);
    else for(i=0;i<pos.count;i++)indices.push(i);
    var groupCount=5*this.topics.length,groups=[],materials=[],self=this;
    for(i=0;i<groupCount;i++)groups.push([]);
    var bounds=new THREE.Box3().setFromBufferAttribute(pos),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3());
    for(i=0;i<indices.length;i+=3){
      var a=indices[i],b=indices[i+1],c=indices[i+2];
      var x=(pos.getX(a)+pos.getX(b)+pos.getX(c))/3;
      var y=(pos.getY(a)+pos.getY(b)+pos.getY(c))/3;
      var z=(pos.getZ(a)+pos.getZ(b)+pos.getZ(c))/3;
      var front=y<-.045,stage;
      if(front&&z>.40&&z<.69&&Math.abs(x)<.29)stage=0;       // eyes, nose, lips
      else if(front&&z>.42&&Math.abs(x)<.43)stage=1;         // facial planes
      else if(z>.67)stage=2;                                // hair mass
      else if(z>.29)stage=3;                                // ears, jaw and neck
      else stage=4;                                         // shoulders and torso
      var nx=(x-center.x)/(size.x||1),ny=(y-center.y)/(size.y||1),nz=(z-center.z)/(size.z||1);
      var field=Math.sin(nx*5.2+ny*3.1+nz*2.3)+Math.sin(ny*6.1-nz*3.7+nx*1.9);
      var topic=Math.max(0,Math.min(this.topics.length-1,Math.floor((field+2)*.25*this.topics.length)));
      groups[stage*this.topics.length+topic].push(a,b,c);
    }
    var reordered=[];geometry.clearGroups();
    groups.forEach(function(group,groupIndex){
      var stage=Math.floor(groupIndex/self.topics.length),topic=groupIndex%self.topics.length;
      var start=reordered.length;Array.prototype.push.apply(reordered,group);
      var mat=new THREE.MeshStandardMaterial({
        color:self.topics[topic].color,emissive:self.topics[topic].color,emissiveIntensity:.04,
        roughness:.84,metalness:0,transparent:true,opacity:0,
        side:THREE.FrontSide,depthWrite:false,polygonOffset:true,
        polygonOffsetFactor:-.45,polygonOffsetUnits:-.45
      });
      mat.skinning=!!mesh.isSkinnedMesh;mat.morphTargets=!!mesh.morphTargetDictionary;
      materials.push(mat);geometry.addGroup(start,group.length,groupIndex);
      self.detailSurfaces.push({material:mat,stage:stage,topic:topic,phase:stage*.91+topic*.37});
    });
    var IndexType=pos.count>65535?Uint32Array:Uint16Array;
    geometry.setIndex(new THREE.BufferAttribute(new IndexType(reordered),1));
    mesh.material=materials;mesh.renderOrder=1.5;
  };
  PerformanceFace.prototype.completeResponse=function(){
    this.responseCount++;
    // Recognition begins with the first answer but resolves deliberately: the
    // central face, surrounding planes and hair reach full opacity around the
    // fourth response, with jaw, neck and torso completing just after them.
    var progress=clamp(this.responseCount/5,0,1),thresholds=[0,.05,0,.16,.28];
    for(var i=0;i<this.detailTargets.length;i++)
      this.detailTargets[i]=Math.max(this.detailTargets[i],clamp((progress-thresholds[i])/.75,0,1));
  };
  PerformanceFace.prototype.addConceptColor=function(text){
    // Hidden speech should not pre-color the portrait before its first reveal.
    if(!this.visible)return;
    var phrase=String(text||""),self=this;
    this.topics.forEach(function(topic,i){
      if(topic.words.test(phrase))self.topicTargets[i]=clamp(Math.max(.88,self.topicTargets[i]+.22),0,1);
    });
  };
  PerformanceFace.prototype.chooseTransitionGesture=function(entering){
    var arrivals=[
      {smile:.20,cheek:.11,tilt:.012},
      {brow:.25,turn:.016,tilt:-.010},
      {blink:.72,smile:.08,chin:.010},
      {smile:.14,brow:.13,turn:-.014},
      {cheek:.10,tilt:.019,turn:.009}
    ];
    var departures=[
      {smile:.20,cheek:.15,tilt:.018},
      {brow:.22,turn:.021,chin:-.012},
      {blink:.78,nod:.025,smile:.06},
      {smile:.13,nod:.034,turn:-.012},
      {cheek:.12,tilt:-.021,brow:.08}
    ];
    var list=entering?arrivals:departures,index=Math.floor(Math.random()*list.length);
    if(index===this.lastGestureIndex)index=(index+1+Math.floor(Math.random()*(list.length-1)))%list.length;
    this.lastGestureIndex=index;this.transitionGesture=list[index];
  };
  PerformanceFace.prototype.updateAssembly=function(progress){
    progress=clamp(progress,0,1);this.assembly=progress;
    this.wireLineSets.forEach(function(set){
      set.lines.geometry.setDrawRange(0,Math.floor((set.indices.length/2)*progress)*2);
    });
    this.fractureSets.forEach(function(set){
      set.lines.geometry.setDrawRange(0,Math.floor(set.indices.length*progress)*6);
    });
  };
  PerformanceFace.prototype.reshuffleAssembly=function(){
    function shufflePairs(a){
      for(var i=a.length/2-1;i>0;i--){
        var j=Math.floor(Math.random()*(i+1)),ia=i*2,ja=j*2;
        var x=a[ia],y=a[ia+1];a[ia]=a[ja];a[ia+1]=a[ja+1];a[ja]=x;a[ja+1]=y;
      }
    }
    this.wireLineSets.forEach(function(set){shufflePairs(set.indices);});
  };
  PerformanceFace.prototype.updateWireNodes=function(){
    this.wireLineSets.forEach(function(set){
      var out=set.lines.geometry.attributes.position.array,a=set.tmpA,b=set.tmpB;
      for(var i=0;i<set.indices.length;i+=2){
        set.mesh.boneTransform(set.indices[i],a);set.mesh.boneTransform(set.indices[i+1],b);
        var p=i*3;out[p]=a.x;out[p+1]=a.y;out[p+2]=a.z;
        out[p+3]=b.x;out[p+4]=b.y;out[p+5]=b.z;
      }
      set.lines.geometry.attributes.position.needsUpdate=true;
    });
    var t=this.clock.elapsedTime,audio=this.speaking?this.level:0,assembly=this.assembly;
    this.fractureSets.forEach(function(set){
      var out=set.lines.geometry.attributes.position.array,p=set.tmp;
      for(var i=0;i<set.indices.length;i++){
        set.mesh.boneTransform(set.indices[i],p);
        var d=set.directions[i],pulse=.82+.18*Math.sin(t*1.35+i*.73)+audio*.42*Math.sin(t*4.1+i*.31);
        var j=set.jitters[i],rag=.16+.18*Math.sin(t*.62+i*1.71),len=set.lengths[i]*assembly*pulse,k=i*18;
        var p1x=p.x+d.x*len*.34+j.x*len*rag,p1y=p.y+d.y*len*.34+j.y*len*rag,p1z=p.z+d.z*len*.34+j.z*len*rag;
        var p2x=p.x+d.x*len*.68-j.x*len*rag*.72,p2y=p.y+d.y*len*.68-j.y*len*rag*.72,p2z=p.z+d.z*len*.68-j.z*len*rag*.72;
        var ex=p.x+d.x*len+j.x*len*rag*.48,ey=p.y+d.y*len+j.y*len*rag*.48,ez=p.z+d.z*len+j.z*len*rag*.48;
        out[k]=p.x;out[k+1]=p.y;out[k+2]=p.z;out[k+3]=p1x;out[k+4]=p1y;out[k+5]=p1z;
        out[k+6]=p1x;out[k+7]=p1y;out[k+8]=p1z;out[k+9]=p2x;out[k+10]=p2y;out[k+11]=p2z;
        out[k+12]=p2x;out[k+13]=p2y;out[k+14]=p2z;out[k+15]=ex;out[k+16]=ey;out[k+17]=ez;
      }
      set.lines.material.opacity=assembly*(.88+audio*.10*(.5+.5*Math.sin(t*3.4)));
      set.lines.geometry.attributes.position.needsUpdate=true;
    });
  };
  PerformanceFace.prototype.setSpeaking=function(on){
    var wasSpeaking=this.speaking;this.speaking=!!on;
    if(on){
      this.postSpeechHold=false;
      // Conversational camera choreography always starts from the synchronized
      // pre-drag pose, even if the visitor left the bust turned to one side.
      if(this.manualOrbitActive){
        this.manualDrag=false;this.manualOrbitActive=false;this.dragPointerId=null;
        this.renderer.domElement.style.cursor="grab";
        if(window.__brainFaceGraphDrag)window.__brainFaceGraphDrag("reset",0,0);
      }
      this.gestureUntil=performance.now()+900;this.target.smile=.08;
    }
    else{
      if(wasSpeaking)this.postSpeechHold=true;
      this.levelTarget=0;this.wordUntil=-1;this.target.smile=.025;
    }
  };
  PerformanceFace.prototype.cueClause=function(text){
    this.setSpeaking(true); this.nodKick=Math.min(.42,this.nodKick+.12);
    if(Math.random()<.52)this.tiltKick=clamp(this.tiltKick+(Math.random()<.5?-1:1)*(.10+Math.random()*.13),-.34,.34);
    this.addConceptColor(text);
    if(/[!?]/.test(text)||Math.random()<.28)this.shrugKick=Math.max(this.shrugKick,.28+Math.random()*.24);
    this.cueWord((text.match(/[A-Za-z']+/)||[""])[0]);
  };
  PerformanceFace.prototype.cueWord=function(word){
    word=(word||"").toLowerCase(); this.wordEnergy=1;
    var round=/[ouqw]/.test(word),wide=/[ei]/.test(word),press=/^[bmp]|[bmp]$/.test(word);
    this.wordShape.jaw=press?.08:(/[aou]/.test(word)?.78:.42);
    this.wordShape.round=round?.76:.05;this.wordShape.wide=wide?.62:.09;
    this.wordShape.cheek=/[ei]/.test(word)?.28:.09;this.wordShape.brow=/[!?]/.test(word)?.24:.04;
    this.wordShape.smile=/\b(good|great|love|fun|happy|beautiful|interesting|yeah|yes)\b/.test(word)?.16:.075;
    this.wordUntil=this.clock.elapsedTime+clamp(.10+word.length*.012,.12,.23);
  };
  PerformanceFace.prototype.attachAudio=function(audio){
    try{
      if(!this.audioContext)this.audioContext=new (window.AudioContext||window.webkitAudioContext)();
      if(this.audioContext.state==="suspended")this.audioContext.resume();
      var source=this.audioContext.createMediaElementSource(audio);
      this.analyser=this.audioContext.createAnalyser();this.analyser.fftSize=256;this.analyser.smoothingTimeConstant=.55;
      this.audioData=new Uint8Array(this.analyser.frequencyBinCount);
      source.connect(this.analyser);this.analyser.connect(this.audioContext.destination);
    }catch(e){this.analyser=null;this.audioData=null;}
  };
  PerformanceFace.prototype.sampleAudio=function(t){
    if(this.analyser&&this.audioData){
      this.analyser.getByteTimeDomainData(this.audioData);var sum=0;
      for(var i=0;i<this.audioData.length;i++){var v=(this.audioData[i]-128)/128;sum+=v*v;}
      return clamp(Math.sqrt(sum/this.audioData.length)*6.15,0,1);
    }
    return this.speaking?(.22+.20*(.5+.5*Math.sin(t*7.1))+.08*(.5+.5*Math.sin(t*11.2+.7))):0;
  };
  PerformanceFace.prototype.blinkAmount=function(t){
    if(t>=this.nextBlink){
      this.blinkStart=t;this.doubleBlink=Math.random()<.18;this.blinkDuration=.12+Math.random()*.05;
      this.nextBlink=t+2.7+Math.random()*3.8+(this.doubleBlink?.25:0);
    }
    var p=(t-this.blinkStart)/this.blinkDuration;
    var b=(p>=0&&p<=1)?Math.sin(Math.PI*p):0;
    if(this.doubleBlink){var q=(t-this.blinkStart-.20)/.12;if(q>=0&&q<=1)b=Math.max(b,Math.sin(Math.PI*q));}
    return b;
  };
  PerformanceFace.prototype.frame=function(){
    requestAnimationFrame(this.frame);var dt=Math.min(.05,this.clock.getDelta()),t=this.clock.elapsedTime;
    this.frameDt=dt;
    if(!this.ready||!this.active)return;
    var transitionPulse=0;
    if(this.phase==="entering"){
      var enterP=clamp((t-this.transitionStart)/1.15,0,1),enterEase=enterP*enterP*(3-2*enterP);
      transitionPulse=Math.sin(Math.PI*enterP);
      this.updateAssembly(enterEase);
      if(enterP>=1){this.phase="present";this.presentStart=t;}
    }else if(this.phase==="exiting"){
      var exitP=clamp((t-this.transitionStart)/1.05,0,1);
      var gestureP=clamp(exitP/.62,0,1),gestureEase=gestureP*gestureP*(3-2*gestureP);
      transitionPulse=Math.sin(Math.PI*gestureEase);
      var retreat=exitP<.30?1:1-(exitP-.30)/.70;
      this.updateAssembly(retreat*retreat*(3-2*retreat));
      if(exitP>=1){
        this.phase="hidden";this.active=false;this.container.classList.remove("on");
        this.container.style.pointerEvents="none";return;
      }
    }else this.updateAssembly(1);
    this.motionBlend=damp(this.motionBlend,this.phase==="present"?1:0,this.phase==="present"?4.6:6.2,dt);
    var bodyMotion=this.motionBlend;
    for(var topicIndex=0;topicIndex<this.topicLevels.length;topicIndex++)
      this.topicLevels[topicIndex]=damp(this.topicLevels[topicIndex],this.topicTargets[topicIndex],3.8,dt);
    for(var detailIndex=0;detailIndex<this.detailLevels.length;detailIndex++)
      this.detailLevels[detailIndex]=damp(this.detailLevels[detailIndex],this.detailTargets[detailIndex],4.8,dt);
    var topicLevels=this.topicLevels,topics=this.topics,assembly=this.assembly,voice=this.speaking?clamp(this.level*1.18,0,1):0;
    // A concept controls how much pigment enters the portrait, but never owns
    // every occupied panel's hue. Keep a spatially distributed palette keyed
    // to the strongest concept so even a single-topic answer produces a bright
    // multicolour field instead of flooding the whole bust amber/yellow.
    var palettePeak=0,dominantTopic=0;
    for(var paletteIndex=0;paletteIndex<topicLevels.length;paletteIndex++){
      if(topicLevels[paletteIndex]>palettePeak){palettePeak=topicLevels[paletteIndex];dominantTopic=paletteIndex;}
    }
    // Concept color behaves like a fluid moving between neighboring mesh zones.
    // Speech accelerates the field; silence leaves it in a slow, living drift.
    this.creepClock+=dt*(this.speaking?(1.40+voice*5.20):.28);
    var creepClock=this.creepClock,topicCount=this.topics.length;
    this.topicSurfaces.forEach(function(surface){
      var left=(surface.topic+topicCount-1)%topicCount,right=(surface.topic+1)%topicCount;
      var donor=topicLevels[left]>=topicLevels[right]?left:right;
      var own=topicLevels[surface.topic],neighbor=topicLevels[donor];
      var wave=.5+.5*Math.sin(creepClock+surface.phase);
      wave=wave*wave*(3-2*wave);
      var creeping=own>.04?0:neighbor*wave*.72;
      var companion=palettePeak*(.20+.34*wave);
      var occupancy=Math.max(own,creeping,companion);
      var colorTopic=(surface.topic+dominantTopic)%topicCount;
      var source=topics[colorTopic],sourceColor=new THREE.Color(source.color),sourceHSL={h:0,s:0,l:0};
      sourceColor.getHSL(sourceHSL);
      var colorPulse=.5+.5*Math.sin(t*(3.15+surface.topic*.11)+surface.phase);
      var saturation=clamp(Math.max(.88,sourceHSL.s+.14)+voice*(.08+.10*colorPulse),.88,1);
      var lightness=clamp(sourceHSL.l+voice*.055*colorPulse,.42,.64);
      surface.material.color.setHSL(sourceHSL.h,saturation,lightness);
      surface.material.emissive.copy(surface.material.color);
      surface.material.emissiveIntensity=.08+voice*(.20+.24*colorPulse);
      surface.material.opacity=assembly*occupancy*clamp(.90+voice*(.095+.095*colorPulse),0,.995);
    });
    var detailLevels=this.detailLevels;
    this.detailSurfaces.forEach(function(surface){
      var left=(surface.topic+topicCount-1)%topicCount,right=(surface.topic+1)%topicCount;
      var donor=topicLevels[left]>=topicLevels[right]?left:right;
      var own=topicLevels[surface.topic],neighbor=topicLevels[donor];
      var wave=.5+.5*Math.sin(creepClock+surface.phase);
      wave=wave*wave*(3-2*wave);
      var creeping=own>.04?0:neighbor*wave*.72;
      var companion=palettePeak*(.16+.28*wave);
      var occupancy=Math.max(own,creeping,companion),active=occupancy>.012;
      var colorTopic=(surface.topic+dominantTopic)%topicCount;
      var faceNeck=surface.stage===0||surface.stage===1||surface.stage===3;
      var base=new THREE.Color(active?topics[colorTopic].color:0xca9177),hsl={h:0,s:0,l:0};
      base.getHSL(hsl);
      var pulse=.5+.5*Math.sin(t*(2.7+surface.stage*.16)+surface.phase);
      surface.material.color.setHSL(hsl.h,active?clamp(Math.max(.88,hsl.s+.14)+voice*.10*pulse,.88,1):hsl.s,active?clamp(hsl.l+voice*.045*pulse,.42,.64):hsl.l);
      surface.material.emissive.copy(surface.material.color);
      surface.material.emissiveIntensity=(active?.04:.01)+voice*.18*pulse;
      // The resolved likeness is solid only across the face and neck. Hair and
      // torso remain empty glass until a concept color occupies their panels.
      surface.material.opacity=assembly*detailLevels[surface.stage]*(faceNeck?1:occupancy);
    });
    // The face itself is the only region without the graph mesh. Neck, hair,
    // shoulders and torso retain their black node-and-edge structure.
    this.wireLineSets.forEach(function(set){set.lines.material.opacity=assembly*(set.facial?0:1);});
    this.levelTarget=this.sampleAudio(t);
    this.level=damp(this.level,this.levelTarget,this.levelTarget>this.level?16:7.5,dt);
    this.speechEnvelope=damp(this.speechEnvelope,this.speaking?1:0,this.speaking?8:5.5,dt);
    this.wordEnvelope=damp(this.wordEnvelope,this.speaking&&t<this.wordUntil?1:0,t<this.wordUntil?17:7,dt);
    this.wordEnergy=damp(this.wordEnergy,0,5.2,dt);
    if(this.speaking){
      var wordMix=this.wordEnvelope*.52,audioJaw=.075+this.level*.68;
      this.target.jaw=clamp(audioJaw*(1-wordMix)+this.wordShape.jaw*wordMix,0,.88);
      this.target.wide=.055+this.level*.10+this.wordShape.wide*this.wordEnvelope*.72;
      this.target.round=.045+this.level*.07+this.wordShape.round*this.wordEnvelope*.76;
      this.target.cheek=.055+this.wordShape.cheek*this.wordEnvelope*.62;
      this.target.brow=.035+this.wordShape.brow*this.wordEnvelope*.42;
      this.target.smile=this.wordShape.smile;
    }
    if(!this.speaking){this.target.jaw=0;this.target.wide=0;this.target.round=0;this.target.cheek=0;this.target.brow=0;this.target.smile=.025;}
    var self=this;Object.keys(this.viseme).forEach(function(k){self.viseme[k]=damp(self.viseme[k],self.target[k],k==="jaw"?11:8,dt);});
    // The scan's lips are topologically sealed. Keep its jaw deformation
    // restrained and let the dedicated aperture create the visible opening.
    this.setMorph("JawOpen",this.viseme.jaw*.22);this.setMorph("MouthWide",this.viseme.wide*.56);
    var gesture=this.transitionGesture||{};
    var expressionSmile=(gesture.smile||0)*transitionPulse,expressionCheek=(gesture.cheek||0)*transitionPulse;
    var expressionBrow=(gesture.brow||0)*transitionPulse,expressionBlink=(gesture.blink||0)*transitionPulse;
    this.setMorph("MouthFunnel",this.viseme.round*.88);this.setMorph("Smile",clamp(this.viseme.smile+expressionSmile,0,1));
    this.setMorph("CheekRaise",clamp(this.viseme.cheek+expressionCheek,0,1));this.setMorph("BrowUp",clamp(this.viseme.brow+expressionBrow,0,1));
    var mouthTarget=this.speechEnvelope*clamp(.035+this.viseme.jaw*.94,0,1);
    this.mouthAperture=damp(this.mouthAperture,mouthTarget,mouthTarget>this.mouthAperture?13:9,dt);
    var mouthOpen=this.mouthAperture;
    if(this.mouthCavity){
      this.mouthCavity.scale.y=.015+mouthOpen*1.12;
      this.mouthCavity.scale.x=.92+this.viseme.wide*.22-this.viseme.round*.24;
    }
    if(this.teeth){
      this.teeth.scale.y=.015+clamp((mouthOpen-.25)*.42,0,.31);
      this.teeth.scale.x=.94+this.viseme.wide*.10-this.viseme.round*.14;
    }

    var blink=Math.max(this.blinkAmount(t),expressionBlink);
    if(this.lids.length)this.lids.forEach(function(o){o.scale.y=.02+blink*.98;});
    else{this.setMorph("Blink_L",blink*.46);this.setMorph("Blink_R",blink*.46);}
    if(t>=this.nextLook){
      if(performance.now()-this.pointer.lastMove<4200)this.lookUntil=t+.75+Math.random()*1.15;
      this.nextLook=t+2.0+Math.random()*3.4;
    }
    this.lookBlend=damp(this.lookBlend,t<this.lookUntil?1:0,t<this.lookUntil?4.8:2.2,dt);
    var idleGazeX=Math.sin(t*.37)*.0038+Math.sin(t*1.13+.7)*.0014;
    var idleGazeY=Math.sin(t*.29+1.2)*.0021+Math.sin(t*.83)*.0008;
    var gazeX=idleGazeX*(1-this.lookBlend)+this.pointer.x*.0105*this.lookBlend;
    var gazeY=idleGazeY*(1-this.lookBlend)-this.pointer.y*.0058*this.lookBlend;
    this.irises.forEach(function(o){o.position.x=o.userData.basePos.x+gazeX;o.position.y=o.userData.basePos.y+gazeY;});

    // A quiet 4.6-second diaphragmatic breath never stops. Speech adds small
    // emphasis gestures but does not replace the idle physiology.
    var breath=Math.sin(t*Math.PI*2/4.6),inhale=(breath+1)*.5*bodyMotion;
    var chest=this.bones.Chest,neck=this.bones.Neck,head=this.bones.Head;
    this.motionEnergy=damp(this.motionEnergy,this.speaking?(.30+.70*this.level):0,this.speaking?4.2:2.8,dt);
    var conversational=this.motionEnergy;
    var cadence=this.speaking?Math.sin(t*2.05)+.28*Math.sin(t*3.45+.8):0;
    var emphasis=this.speaking?clamp(this.nodKick*1.2+this.shrugKick*.45,0,1):0;
    if(chest){chest.scale.x=1+inhale*.012;chest.scale.z=1+inhale*.018;chest.position.y=chest.userData.basePos.y+inhale*.004;}
    if(chest){
      chest.rotation.z=chest.userData.baseRot.z+bodyMotion*(Math.sin(t*.43)*.011+Math.sin(t*1.12+.8)*.004+conversational*cadence*.010);
      chest.rotation.y=chest.userData.baseRot.y+bodyMotion*(Math.sin(t*.31+1.4)*.009+conversational*Math.sin(t*1.72)*.018+emphasis*.009);
    }
    this.nodKick=damp(this.nodKick,0,1.8,dt);this.tiltKick=damp(this.tiltKick,0,1.45,dt);this.shrugKick=damp(this.shrugKick,0,1.7,dt);
    if(head){
      head.rotation.x=head.userData.baseRot.x+bodyMotion*(Math.sin(t*.52)*.010-this.nodKick*.046+conversational*cadence*.012-emphasis*.008-this.pointer.y*this.lookBlend*.032)+(gesture.nod||0)*transitionPulse+(gesture.chin||0)*transitionPulse;
      head.rotation.y=head.userData.baseRot.y+bodyMotion*(Math.sin(t*.27+.6)*.016+conversational*Math.sin(t*1.7+.4)*.021+this.pointer.x*this.lookBlend*.072)+(gesture.turn||0)*transitionPulse;
      head.rotation.z=head.userData.baseRot.z+bodyMotion*(Math.sin(t*.31)*.019+Math.sin(t*.71+1.2)*.007+this.tiltKick*.046+conversational*Math.sin(t*2.33)*.009)+(gesture.tilt||0)*transitionPulse;
    }
    if(neck){
      neck.rotation.x=neck.userData.baseRot.x+bodyMotion*(conversational*cadence*.006-this.pointer.y*this.lookBlend*.010)+(gesture.nod||0)*transitionPulse*.32;
      neck.rotation.y=neck.userData.baseRot.y+bodyMotion*(conversational*Math.sin(t*1.27)*.007+this.pointer.x*this.lookBlend*.020);
      neck.rotation.z=neck.userData.baseRot.z+bodyMotion*(Math.sin(t*.25+.7)*.007+conversational*Math.sin(t*1.95)*.005)+(gesture.tilt||0)*transitionPulse*.24;
    }
    ["Shoulder_L","Shoulder_R"].forEach(function(n,i){
      var b=self.bones[n];if(!b)return;
      var side=i?-1:1;
      var easyFloat=bodyMotion*Math.sin(t*.82+i*.72)*.0042;
      var talkBounce=bodyMotion*conversational*(.0075*Math.sin(t*2.45+i*.55)+.0045+emphasis*.004);
      b.position.y=b.userData.basePos.y+inhale*.003+bodyMotion*self.shrugKick*.024+easyFloat+talkBounce;
      b.rotation.z=b.userData.baseRot.z+bodyMotion*side*(Math.sin(t*.58+i*.45)*.008+conversational*(.011+.006*Math.sin(t*2.7+i)));
    });
    this.updateWireNodes();
    this.applyGraphView();
    this.controls.update();this.renderer.render(this.scene,this.camera);
  };
  PerformanceFace.prototype.open=function(){
    if(this.visible)return;this.visible=true;this.active=true;this.phase="entering";
    this.transitionStart=this.clock.elapsedTime;this.chooseTransitionGesture(true);this.reshuffleAssembly();this.updateAssembly(0);
    this.container.classList.add("on");this.container.style.pointerEvents="auto";this.resize();
  };
  PerformanceFace.prototype.close=function(){
    if(!this.visible)return;this.visible=false;this.active=true;this.phase="exiting";
    this.transitionStart=this.clock.elapsedTime;this.chooseTransitionGesture(false);this.reshuffleAssembly();this.container.style.pointerEvents="none";
  };
  PerformanceFace.prototype.toggle=function(){this.visible?this.close():this.open();};

  window.ErnestPerformanceFace=PerformanceFace;
})();
