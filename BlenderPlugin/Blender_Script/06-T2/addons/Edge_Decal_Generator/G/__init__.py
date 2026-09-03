Rmin,Rmax,SP,TB,ZW,EW=(4,5,0),(5,3,0),'BV11otL64EWD','🌸','边缘贴花','Edge Decal Generator'
BD={'ocd_addon':'BV14Yhc6tEps','xdecal':'BV1PFsCzzEV4','decalmachine':'BV11RmXBGEEV','alt_tab_easy_decals':'BV1Q8P7z8E97','lazy_decals':'BV1umSYBPEbf','align_edges':'BV1wHFhzzEtv','decal_master':'BV1QGzEBeExS','mix_damage':'BV19niKBfEhN','stamp_it':'BV164wWe8EAN','poly_damage':'BV153nZz9EPw','slide_edge':'BV12QwYePEwa','import_as_decal':'BV1dHK8z3Ekb','edge_extrude':'BV114421S7Kw','scatter_on_edges':'BV1BZ4217782',}
import bpy,json,blf,unicodedata,contextlib,re,os,bmesh,sys,time,webbrowser,addon_utils,bpy.utils.previews;from bpy.props import BoolProperty,CollectionProperty,EnumProperty,FloatProperty,FloatVectorProperty,IntProperty,PointerProperty,StringProperty;from bpy.types import AddonPreferences,Modifier,Operator,Panel,PropertyGroup,WindowManager,Scene;from pathlib import Path;from os.path import dirname as DP,join as JP,basename as BP,realpath as RP,exists as EP,splitext as ST;from functools import lru_cache,wraps;from threading import Lock
AD=__package__[:-2];AK,FP,IT,CL,VE,BL,PC={},DP(DP(RP(__file__))),[],[],bpy.app.version,"https://www.bilibili.com/video/",{};BT=ZW + " (" + EW + ")";YP_GLOBAL=Path(JP(DP(FP),"Y"));global IC;IC=bpy.utils.previews.new();_CACHE_LOCK=Lock();_GLOBAL_CACHE_CONTAINER={"os_cache":{"plugins_dir_list":None,"cache_timestamp":0,"cache_expire":30},"plugin_translation":{},"debounce_cache":{}}
def GMV(M,key):return M[key] if VE<(5,2,0) else float(getattr(M.properties.inputs,key).value)
def SMV(M,key,val):exec('try:\n\tM[key]=val\nexcept:\n\tM[key]=int(val)' if VE<(5,2,0) else 'getattr(M.properties.inputs,key).value=val')
def GMP(M,k):return (M,f'["{k}"]') if VE<(5,2,0) else ((getattr(M.properties.inputs,k),'value') if hasattr(M.properties.inputs,k) else (M,k))
def SEM(N='OBJECT'):bpy.ops.object.mode_set(mode=N) if bpy.context.active_object and bpy.context.active_object.mode !=N else None
def GPW():return int(bpy.context.area.width / bpy.context.preferences.view.ui_scale)
def SAF(F,*A,**K):
	try:R=F(*A,**K);return R,None
	except Exception as e:print(f"✖异常类型：{type(e).__name__} | 异常信息：{e}");return None,str(e)
def FAR(t='VIEW_3D'):return next((x for x in bpy.context.screen.areas if x.type==t),None)
def SCV():
	s=bpy.context.scene;c=s.camera;area=FAR()
	if not c:a=FAR();bpy.ops.object.camera_add();c=r=None;c=bpy.context.active_object;r=a.spaces.active.region_3d;c.rotation_euler=r.view_rotation.to_euler();c.location=r.view_matrix.inverted().translation
	s.camera=c;KX(c,D=1)
	o=next(({'window':w,'screen':w.screen,'area':FAR(),'region':r,'scene':s}for w in bpy.context.window_manager.windows if FAR() for r in FAR().regions if r.type=='WINDOW'),None)
	with bpy.context.temp_override(**o):
		if area and area.spaces.active.region_3d.view_perspective!='CAMERA':SAF(bpy.ops.view3d.view_camera)
		SAF(lambda: setattr(c.data, 'show_limits',True));SAF(lambda: setattr(bpy.context.space_data, 'lock_camera',True));SAF(bpy.ops.view3d.view_center_camera)
	KX([x for x in bpy.context.visible_objects if x.type=="MESH"],D=1,V=1)
def MII(L):global IT;IT=[(j,"",g(j,T="C"),I(j),i) for i,j in enumerate(L)];return IT
def MIT(L):global IT;IT=[(j,j.replace('_',' ').title(),g(j,T="C"),"",i) for i,j in enumerate(L)];return IT
def GG(L,N=0):C=L.column();G=C.grid_flow(row_major=1,align=0) if N==0 else C.grid_flow(row_major=1,align=0,columns=N);G.alignment='CENTER';return G
def GPDL():
	T=time.time();C=_GLOBAL_CACHE_CONTAINER["os_cache"]
	with _CACHE_LOCK:
		if (C["plugins_dir_list"] is None or T - C["cache_timestamp"] > C["cache_expire"]):C["plugins_dir_list"]=os.listdir(DP(FP));C["cache_timestamp"]=T
	return C["plugins_dir_list"]
def WJDX(P,M='r',C="B"):
	with open(P,M,encoding='utf-8') as f:return f.read().strip() if M=='r' else f.write(C)
if not YP_GLOBAL.exists():WJDX(YP_GLOBAL,'w')
def get_Y_value():return WJDX(YP_GLOBAL,"r")
def I(N):global IC;P_path=N if os.path.isfile(N) else JP(FP,"G",str(N)+".png");return 1 if not EP(P_path) or (IC.get(P_path) is None and not IC.load(P_path,P_path,"IMAGE")) else IC[P_path].icon_id
def UPL(s,_):WJDX(YP_GLOBAL,"w",_.window_manager.Y);bpy.context.preferences.view.language=('zh_CN' if bpy.app.version<(4,0,0) else 'zh_HANS') if _.window_manager.Y in ('B','C') else 'en_US';bpy.context.preferences.view.use_translate_new_dataname=0
YYY=get_Y_value()
if not hasattr(bpy.types.WindowManager,'Y'):bpy.types.WindowManager.Y=bpy.props.EnumProperty(name="Language",description="语言切换",items=[("A","English","英文",I("A"),0),("B","Chinese","中文",I("B"),1),("C","English & Chinese","中英对照",I("C"),2),("D","Chinese & English","英中对照",I("D"),3)],default=YYY,update=UPL)
def debounce(plugin_id):
	def decorator(func):
		@wraps(func)
		def wrapper(*args,**kwargs):
			T=time.time();C=_GLOBAL_CACHE_CONTAINER["debounce_cache"];L=C.get(plugin_id,{}).get("last_load",0)
			if T - L < 1.0:return
			result=func(*args,**kwargs)
			with _CACHE_LOCK:
				if plugin_id not in C:C[plugin_id]={}
				C[plugin_id]["last_load"]=T
			return result
		return wrapper
	return decorator
def LPTC(fp):
	plugin_id=BP(FP);C=_GLOBAL_CACHE_CONTAINER["plugin_translation"]
	@debounce(plugin_id)
	def _inner_load():
		TSV=Path(fp) / "G" / "list.tsv";P=Path(fp) / "G" / f"{plugin_id}_translation.json"
		try:
			tsv_mtime=os.path.getmtime(TSV)
		except FileNotFoundError:
			with _CACHE_LOCK:C[plugin_id]={"zd":{},"patt":None,"tsvt":0};return
		with _CACHE_LOCK:plugin_trans=C.get(plugin_id,{});cached_tsvt=plugin_trans.get("tsvt",0)
		if tsv_mtime==cached_tsvt and P.exists():
			with open(P,"r",encoding="utf-8") as f:zd_data=json.load(f)
			patt=re.compile('|'.join(map(re.escape,zd_data.keys()))) if zd_data else None
			with _CACHE_LOCK:C[plugin_id]={"zd":zd_data,"patt":patt,"tsvt":tsv_mtime};return
		if TSV.exists():
			with open(TSV,"r",encoding="utf-8") as f:zd_data={k:v for k,v in (x.strip().split('\t') for x in f if x.strip())}
			with open(P,"w",encoding="utf-8") as f:json.dump(zd_data,f,ensure_ascii=False,indent=2)
			patt=re.compile('|'.join(map(re.escape,zd_data.keys()))) if zd_data else None
			with _CACHE_LOCK:C[plugin_id]={"zd":zd_data,"patt":patt,"tsvt":tsv_mtime}
		else:
			with _CACHE_LOCK:C[plugin_id]={"zd":{},"patt":None,"tsvt":0}
	_inner_load()
	with _CACHE_LOCK:return C.get(plugin_id,{"zd":{},"patt":None})
def X(S,_,L):
	d=BP(FP);b=[GPDL()];GL(L,"Relevant Addon",icon_value=I("DD"));G=L.row();j=0;W=1 if GPW()<700 else 2 if GPW()<950 else 3 if GPW()<1200 else 4 if GPW()<1500 else 5 if GPW()<1800 else 6
	for k,v in BD.items():
		j=j+1;c=any((k in i or k.lower() in i) for i in b[0]);n=EP(JP(FP,"..",k,"blender_manifest.toml"));m=AD.replace(d,k) if n else k;A=0 if not c else (addon_utils.check(k)[1] or addon_utils.check(m)[1]);t=k.replace("_"," ").title()
		if not c:GO(G,"wm.url_open",icon_value=I("down"),text=t).url=BL + v
		elif A==0:GO(G,"preferences.addon_enable",icon_value=I("E1" if n else"E2"),text=t).module=m
		else:R=G.row();GO(R,"preferences.addon_disable",icon_value=I("E3" if n else"E4"),text="").module=m;GO(R,"preferences.addon_show",icon='SETTINGS',text=t).module=m
		if j % W==0:G=L.row()
if bpy.app.version < Rmin:raise RuntimeError(f"最低需要 Blender {'.'.join(map(str,Rmin))}")
def EV(L,K,T=""):
	if K.startswith("_"):L.label(text=T,icon_value=I(K))
	else:L.label(text=T,icon=f"EVENT_{K.upper()}")
def IF(s):return "TRIA_DOWN" if s else "TRIA_RIGHT"
def DR(S,_,L):G=L.grid_flow(row_major=1,align=1,columns=5);G.label(text="",icon_value=I("CH"));GE(G,P(),"X")
def DH(S,_,L):
	G=L.grid_flow(row_major=1,align=1,columns=7);G.prop(_.window_manager,"Y",text="",expand=1);G.operator("wm.url_open",text="",icon_value=I("E")).url=BL+SP;G.operator("wm.url_open",text="",icon_value=I("F")).url="https://space.bilibili.com/454791153/video"
	if P().V and VE>Rmax:L.alert=1;GL(L,f"{BT}\nWhen publishing Blender The highest support is {Rmax[0]}.{Rmax[1]}.{Rmax[2]},current version{bpy.app.version_string}Belonging to subsequent versions，Please test the usability yourself，If you have any questions,please click on the blue button above 📺 icon，Take screenshots of relevant videos on Bilibili and leave a message，I will try my best to update and upgrade as much as possible！Charging users are given priority consideration🤔");GP(L,P(),"V",icon="INFO")
def P():return bpy.context.preferences.addons[AD].preferences
def DHP(S,_,L):L.operator("preferences.addon_show",icon_value=I("S"),emboss=1,depress=1,text="").module=AD
def DIC(S,_):S.layout.operator("wm.url_open",icon_value=I("0"),text="").url=BL+SP
def _UPC(fp):LPTC(fp)
def g(E,T=''):
	M=T if T else get_Y_value()
	if not E or len(E) < 2 or ' ›' in E or M=='A':return E
	C=LPTC(FP);zd=C["zd"];patt=C["patt"];El=E.lower();Z=patt.sub(lambda m:zd.get(m.group(),m.group()),El) if patt else El;Z=re.sub(r'(?<=[〇-龟])\s+(?=[〇-龟])','',Z)
	return Z if M=='B' else f"{Z} ›{E}" if M=='C' else f"{E} ›{Z}" if M=='D' else E
IT=dict()
def ITM(I,N,D,P,U):
	A=str(I)+"\0"+str(N)+"\0"+str(D)+"\0"+str(P)+"\0"+str(U)
	if not A in IT:IT[A]=(I,N,D,P,U)
	return IT[A]
def FK(L,K,T=""):
	km,kmi=AK[K];M=bpy.context.window_manager.keyconfigs.user.keymaps[km.name].keymap_items
	for k in M:
		if kmi.idname==k.idname:
			for n in dir(kmi.properties):
				if not n in ["bl_rna","rna_type"] and not n[0]=="_":
					if n in kmi.properties and n in k.properties and kmi.properties[n]!=k.properties[n]:T=0
			R=L.row();R.label(text=g(T if T else k.name),icon_value=I("K"));R.prop(k,'type',text="",full_event=1);break
def PE(P):
	import inspect as i;f=i.currentframe().f_back
	try:eval(P,f.f_globals,f.f_locals);return 1
	except:return 0
	finally:del f
def IZ(N):return any('〇' <=i <='龟' for i in N)
def GC(L):
	IT='A';T0=0
	try:W=max(100,bpy.context.region.width - 60)
	except:W=600
	if VE < (4,0,0):blf.size(T0,12,bpy.context.preferences.system.dpi)
	else:blf.size(T0,12)
	while True:
		T1,_=blf.dimensions(T0,IT)
		if T1 >=W:break
		IT += 'A'
	return int(len(IT) * 0.7)
def CT(s):return sum(2 if unicodedata.east_asian_width(c) in ['F','W'] else 1 for c in s)
def UV(S,_):bpy.ops.object.editmode_toggle();bpy.ops.uv.smart_project();bpy.ops.object.editmode_toggle()
def WT(T,W,I=0):
	l=[];c="";v=W - 8 if I else W
	for x in list(T):
		T0=c + x;n=CT(T0)
		if n <=v:c=T0
		else:l.append(c);c=x;v=W
	if c:l.append(c)
	return l
def GL(L,T,**K):
	def _W(R,t,Z,W,x,L):t_esc=t.replace("'", "\\'"); Z_esc=Z.replace("'", "\\'");exec(f"if CT(g('{t_esc}'))<{W}:\n\tR.label(text=g('{t_esc}'))\nelse:\n\tO=WT('{t_esc}',{W}) if '{x}'=='A' else WT('{Z_esc}',{W}) if '{x}'=='B' else WT('{Z_esc}',{W})+WT('{t_esc}',{W}) if '{x}'=='C' else WT('{t_esc}',{W})+WT('{Z_esc}',{W}) if '{x}'=='D' else []\n\tfor i in O:\n\t\tR.label(text=i)\n\t\tR=L.row()")
	R=L.row();W=GC(L);x=get_Y_value();T=T if isinstance(T,list)else T.split('\n')if'\n'in str(T)else[T];t0=T[0];Z0=g(t0,"B")
	if'icon'in K or'icon_value'in K:R.label(**K,text="")
	_W(R,t0,Z0,W,x,L)
	for t in T[1:]:R=L.row();Z=g(t,"B");_W(R,t,Z,W,x,L)
def GO(L,O,**K):
	T=K.pop('text',None)
	if T is None:C=next((cls for cls in bpy.types.Operator.__subclasses__() if getattr(cls,'bl_idname','').lower()==O.lower()),None);T=C.bl_label if C else O.replace('_',' ').title()
	return L.operator(O,text=g(T),**K)
def GOE(L,P,E):
	C=next((c for c in bpy.types.Operator.__subclasses__() if getattr(c,'bl_idname',None)==P),None);I=None
	if not C:print(f"未找到运算符: {P}");return
	if hasattr(C,'__annotations__') and E in C.__annotations__:
		A=C.__annotations__[E]
		if hasattr(A,'keywords') and 'items' in A.keywords:I=A.keywords['items']
	if I is None:
		try:
			O=C()
			if hasattr(O,'bl_rna'):
				R=O.bl_rna.properties.get(E)
				if R and R.type=='ENUM':I=[(i.identifier,i.name,i.description,i.icon,i.value)for i in R.enum_items]
		except:
			if hasattr(C,'bl_rna'):
				R=C.bl_rna.properties.get(E)
				if R and R.type=='ENUM':I=[(i.identifier,i.name,i.description,i.icon,i.value)for i in R.enum_items]
	if not I:print(f"运算符 {P} 不存在有效的枚举属性 {E}");return
	[setattr(L.operator(P,text=g(e[1]if len(e)>=2 else e[0]),icon=e[3]if len(e)>=4 else 'NONE'),E,e[0])for e in I]
def GM(L,O,**K):
	T=K.pop('text',None)
	if T is None:
		if isinstance(O,str):C=next((cls for cls in bpy.types.Menu.__subclasses__() if getattr(cls,'bl_idname','')==O),None);T=C.bl_label if C else O.replace('_',' ').title()
		elif hasattr(O,'bl_label'):T=O.bl_label
	if T is not None:K['text']=g(T) if T else T
	return L.menu(O,**K)
def GE(L,D,E,S=1,**K):
	P=D.rna_type.properties.get(E) if hasattr(D,'rna_type') else D.bl_rna.properties.get(E) if hasattr(D,'bl_rna') else None;T=K.pop('text',None);G=GG(L);G.scale_x=S
	if T:GL(G,T if T.endswith(":") else T+":")
	if P and getattr(P,'enum_items',None):
		for i in P.enum_items:G.prop_enum(D,E,i.identifier,text=g(i.name))
	else:GP(L,D,E,**K)
def GU(L,D,E,N,**K):
	T=K.pop('text',None)
	if not T and hasattr(D,'rna_type') and E in D.rna_type.properties:
		e=D.rna_type.properties[E].enum_items;m=next((i for i in e if i.identifier==N),None);T=m.name if m else N
	if T is None:T=getattr(E,'name',N)
	return L.prop_enum(D,E,N,text=g(T),**K)
def GP(L,D,E,**K):
	if "full_event" in K:return L.prop(D,E,text=g(text),**K)
	T,_=SAF(D.bl_rna.properties.get,E,None)
	text=K.pop('text',None)
	if not text and "_expand" not in E and "_filter" not in E:text=T.name if T else E.replace('_',' ').title()
	return L.prop(D,E,text=g(text),**K)
def GPS(L,D,A,SD,SP,**K):K.pop('item_search_property',None);return L.prop_search(D,A,SD,SP,**K)
def SGP(L,S,P):return [GP(L,S,i) for i in P]
def GR(S,*K):
	t='INFO';m=None
	if len(K)==1:m=K[0]
	elif len(K)==2:
		if isinstance(K[0],(set,dict,list)):t=next(iter(K[0])) if K[0] else 'INFO';m=K[1]
		elif K[0].upper() in {'INFO','WARNING','ERROR','DEBUG'}:t=K[0].upper();m=K[1]
		else:m=K[0];t=K[1].upper()
	if m is None:return
	msg=str(m) if any('\u4e00'<=c<='\u9fff' for c in str(m)) else g(m)
	S.report({t},msg)
def MK(m):
	try:__import__(m)
	except:
		import sys,subprocess as s,importlib as l
		try:s.check_call([sys.executable,"-m","pip","install",m])
		except:return 0
		finally:globals()[m]=l.import_module(m)
	return 1
def KX(n,V=0,D=0):
	A=None;B=bpy.context.view_layer.objects.active;SO=[];SEM('OBJECT')
	C=n if isinstance(n,list) else [n];D=1 if isinstance(n,list) else D
	if D:bpy.ops.object.select_all(action='DESELECT')
	for x in C:
		if isinstance(x,str):
			o=next((i for i in bpy.context.visible_objects if i.name.startswith(x)),None)
			if not o:print(f"警告：未找到以'{x}'开头的可见对象");continue
		else:
			if x not in bpy.context.visible_objects:print(f"警告：对象{x.name}不可见或不存在");continue
			o=x
		o.select_set(True);SO.append(o)
	if not SO:print("警告：无有效对象可选中");return
	bpy.context.view_layer.objects.active=SO[0]
	if V and SO:
		view3d_area=FAR()
		if not view3d_area:print("警告：未找到3D视图区域，跳过框显");return
		try:
			with contextlib.suppress(RuntimeError):
				T=bpy.context.copy();T['area']=view3d_area;T['region']=view3d_area.regions[-1]
				with bpy.context.temp_override(**T):bpy.ops.view3d.view_selected(use_all_regions=False)
		except Exception as e:print(f"警告：框显操作失败 - {str(e)}")
def EIT(L,D,E,T,N=1):
	G=L.grid_flow(row_major=1,align=1,columns=N)
	for i in T:G.prop_enum(D,E,i,text=g(i.capitalize().replace("_"," ")))
def EB(N):
	for i in [f"bl_ext.blender_org.{N}",f"bl_ext.user_default.{N}",AD.replace(BP(FP),N),N]:
		if i in bpy.context.preferences.addons:return
		try:bpy.ops.preferences.addon_enable(module=i);return
		except RuntimeError as e:continue
	raise RuntimeError(f"无法启用插件：{N}（所有命名空间均失败）请尝试在首选项中手动启用该插件")
def CKD(N):
	for i in [N,AD.replace(BP(FP),N),f"bl_ext.user_default.{N}",f"bl_ext.blender_org.{N}"]:
		if addon_utils.check(i)[1]:return True
	return False
def CKB(L,K):
	if not CKD(K):GO(L,"preferences.addon_enable",text=f"Setup {K}",icon='URL').module=AD.replace(BP(FP),K)
def CKA(L,K,V,O=None):
	A=GPDL();B=any(K==p for p in A);KT=K.replace('_',' ').title()
	if not B:GO(L,"wm.url_open",text="Download:"+KT,icon_value=I(K)).url=f"{BL}{V}";return
	elif not CKD(K):GO(L,"preferences.addon_enable",text="Enable:"+KT,icon_value=I(K)).module=AD.replace(BP(FP),K);return
	elif O:GO(L,O,icon_value=I(K))
def TEO():return len([x for x in bpy.context.selected_objects if x.type in('MESH','CURVE')])>1
def DBG(N):print (f"【{N}】{str(N)}")
def RCL(l):
	if not isinstance(l,(list,tuple)):SAF(bpy.utils.register_class,l);return
	for i in (l if isinstance(l,(list,tuple)) else tuple(l)):SAF(bpy.utils.register_class,i)
def UCL(l):
	if not isinstance(l,(list,tuple)):SAF(bpy.utils.unregister_class,l);return
	for i in reversed(l if isinstance(l,(list,tuple)) else tuple(l)):SAF(bpy.utils.unregister_class,i)
def RTO(T,**K):SAF(bpy.utils.register_tool,T,**K);
def UTO(T):SAF(bpy.utils.unregister_tool,T);
def DAS(L,N="Scene"):[delattr(getattr(bpy.types,N),i)for i in L if hasattr(getattr(bpy.types,N),i)]
def UPS(S,_):
	if not _ or not hasattr(_,'space_data'):return
	if P().X=="SOLID":SAF(lambda: setattr(_.space_data.shading,'type','SOLID'));SAF(lambda: setattr(_.space_data.shading,'color_type','TEXTURE'))
	elif P().X=="MATERIAL":SAF(lambda: setattr(_.space_data.shading,'type','MATERIAL'))
	elif P().X=="EEVEE":SAF(lambda: setattr(_.space_data.shading,'type','RENDERED'));SAF(lambda: setattr(_.scene.render,'engine','BLENDER_EEVEE_NEXT' if (4,2)<VE<(5,0) else 'BLENDER_EEVEE'))
	elif P().X=="Cycles":EB("cycles");SAF(lambda: setattr(_.space_data.shading,'type','RENDERED'));SAF(lambda: setattr(_.scene.render,'engine','CYCLES'));SAF(lambda: setattr(_.scene.cycles, 'device','GPU'))
def GSP(S,L,O,n="",t=""):
	if bpy.app.version>=(4,2,3):h,p=L.panel_prop(S,n);GL(h,t);return p
	else:GP(L,S,n,text=t,emboss=0,toggle=1,icon="TRIA_DOWN" if O else "TRIA_RIGHT");return O
def UPG(s,_):
	if len(P().C.strip())=="":return
	p=[c for c in bpy.types.Panel.__subclasses__() if hasattr(c,"bl_region_type") and c.bl_region_type =="UI" and c.__module__.startswith(AD)];d={c.bl_idname:getattr(c,"bl_parent_id","") for c in p};q=[c for c in p if not d[c.bl_idname]];o=[];r=set()
	while q:c=q.pop(0);o.append(c);[q.append(next(x for x in p if x.bl_idname==k)) for k,v in d.items() if v==c.bl_idname]
	for c in reversed(o):SAF(bpy.utils.unregister_class,c)
	for c in o:
		c.bl_category=P().C;pid=getattr(c,"bl_parent_id","")
		if pid and pid not in r:continue
		SAF(bpy.utils.register_class,c);r.add(c.bl_idname)