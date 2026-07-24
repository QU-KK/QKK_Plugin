_Z='SIMPLEBAKE_PT_LanguagePanel'
_Y='SIMPLEBAKE_AddonPreferences'
_X='Support '
_W='汉化进行中，优化改错请私B站：三叔作蜜不甜当醋不酸。'
_V='SIMPLEBAKE_PT_main_panel'
_U='zh_HANT'
_T='simplebake'
_S='https://space.bilibili.com/3690998511175919/upload/video'
_R='More Plugins'
_Q='https://www.bilibili.com/video/BV1xsorBiEjR/'
_P='Video Tutorial'
_O='FUND'
_N='FINISHED'
_M='zh_CN'
_L='draw'
_K=None
_J='simplebake.show_fund_image'
_I='bl_idname'
_H='English'
_G='wm.url_open'
_F='中文'
_E='simplebake.set_english'
_D='simplebake.set_chinese'
_C='zh_HANS'
_B=False
_A=True
import bpy,os,gettext,tempfile,base64
ENABLE_PANEL_MODULE=_A
ENABLE_MENU_MODULE=_B
ENABLE_PREFERENCES_MODULE=_A
ENABLE_CREATE_PREFERENCES_MODULE=_B
ENABLE_IMPORT_MODULE=_B
ENABLE_EXPORT_MODULE=_B
ENABLE_TEMPORARY_PANEL_MODULE=_B
ENABLE_OVERLAY_PANEL_MODULE=_B
SILENT_MODE=_A
def silent_print(*A,**B):
	if not SILENT_MODE:print(*A,**B)
FUND_IMAGE_BASE64='\n/9j/4AAQSkZJRgABAQEAeAB4AAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAEsASwDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3m5uYrSBppmwg9qWG4juIFmjOUbpxRcQxXEJjmUMh7UsMMcEKxRKFRegFAC+YPRv++TR5g9G/75NPooAZ5g9G/wC+TR5g9G/75NPooAZ5g9G/75NHmD0b/vk0+igBnmD0b/vk0eYPRv8Avk0+igBnmD0b/vk0eYPRv++TT6KAGeYPRv8Avk0eYPRv++TT6KAGeYPRv++TR5g9G/75NPooAZ5g9G/75NHmD0b/AL5NPooAZ5g9G/75NHmD0b/vk0+igBnmD0b/AL5NHmD0b/vk0+igBnmD0b/vk0eYPRv++TT6KAGeYPRv++TR5g9G/wC+TT6KAGeYPRv++TR5g9G/75NPooAZ5g9G/wC+TR5g9G/75NPooAZ5g9G/75NHmD0b/vk0+igBnmD0b/vk0eYPRv8Avk0+igBnmD0b/vk0ocE9/wAQadRQBVOoWy3otC/709scfTNWqrNZWxvFuWiHndA1WaAGv0H1H86dTX6D6j+dOoAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigBj/AHk+v9DT6a33k+v9DTqAGv0H1H86dTX6D6j+dOoAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigBrfeT6/wBDTqa33k+v9DTqAGv0H1H86dTX6D6j+dOoAKKKKACiiigAooooAKKKKACiiigAooooAKKYssbOyK6l0xuUHkZ6Zri/E/inUfDXjvw9DceV/wAI9qm60dyvzRXOcoS3oeBj6mgDrL/U7HS44pL+7htkllWGNpXChnb7qjPc1Ylk8qF5NrPtUnaoyTjsPeuU+JXhe58W+CrrTrEqL9XjntSzbQHVs9e3G4fjXT2guPsEAudoufKXzdvI345x7ZoAg0bUv7Y0i21D7HdWfnru+z3ceyVOcYZe1Mh1Yza9daX9gvE+zxJJ9qePEMm7Pyq3cjHIrlvhLrmpa94KM+rXLXN7DeTQSSsACdrcdPQGupsb2/uNS1G3utMa2trd0W2uTKrC5BXJIUcrg8c0ATXup2OnPbJe3cNu11KIIBI4XzJD0Uepq3XI67Y6Lr3jjRLK8luxqGlKdShiSM+U4yFBZsYyCAQM5rb12/Wz08wpqNrY312Tb2UlzgqZ2B2jH8XPagDToqvYpdR6fbpfSpNdrEomkjTarvj5iB2BOeKmjkSVA8bq6noynIoAdRRRQAUUUUAFFFFABRRRQAUUUUAFFFFADW+8n1/oadTW+8n1/oadQA1+g+o/nTqa/QfUfzp1ABRRRQAUUUUAFFFFABRRRQAUUUUAFUtT1jTdFtftOqX9tZQZwJLiUICfQZ6mlOracNWGlG+txqBj80WpkHmFP723rjg15rc2setfFPxONRsYNSv9LsITounXbAROGQl3APGS+AWxxQB1VtJZPqC674TttO1AancRpql7Hdj5Y0UgN3BIHGOKk8d+HIvGfgm906F0aZ0860lV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\n'
language_mapping={_M:_C,'zh_TW':_U,_C:_M,_U:'zh_TW'}
def get_compatible_lang(lang):
	A=lang
	if bpy.app.version>=(4,0,0):return A
	else:return language_mapping.get(A,A)
def set_language(language):
	B=language;A=bpy.context.preferences;C=get_compatible_lang(B)
	if B==_C or B==_M:A.view.language=C;A.view.use_translate_interface=_A;A.view.use_translate_tooltips=_A;silent_print('切换到中文')
	else:A.view.language=C;A.view.use_translate_interface=_A;A.view.use_translate_tooltips=_A;silent_print('Switched to English')
class SIMPLEBAKE_OT_SetChinese(bpy.types.Operator):
	bl_idname=_D;bl_label='Set Chinese';bl_description='Set interface to Chinese'
	def execute(A,context):set_language(_C);return{_N}
class SIMPLEBAKE_OT_SetEnglish(bpy.types.Operator):
	bl_idname=_E;bl_label='Set English';bl_description='Set interface to English'
	def execute(A,context):set_language('en_US');return{_N}
class SIMPLEBAKE_OT_ShowFundImage(bpy.types.Operator):
	bl_idname=_J;bl_label='Support San Shu';bl_description="Show tip QR code — Support San Shu's work"
	def execute(B,context):
		D='INFO'
		try:
			G=base64.b64decode(FUND_IMAGE_BASE64.replace('',''));H=tempfile.gettempdir();A=os.path.join(H,'simplebake_fund_qrcode.jpg')
			with open(A,'wb')as I:I.write(G)
			silent_print(f"赞赏码图片已保存到: {A}");B.report({D},f"赞赏码图片已保存到临时目录");import platform as J,subprocess as E;F=J.system()
			try:
				if F=='Windows':os.startfile(A)
				elif F=='Darwin':E.call(['open',A])
				else:E.call(['xdg-open',A])
				B.report({D},'已在图片查看器中打开赞赏码')
			except Exception as C:silent_print(f"无法使用默认程序打开图片: {C}");B.report({D},f"请手动查看图片: {A}")
		except Exception as C:silent_print(f"显示赞赏码图片时出错: {C}");B.report({'ERROR'},f"显示赞赏码图片时出错: {C}")
		return{_N}
class SIMPLEBAKE_MT_LanguageMenu(bpy.types.Menu):
	bl_label='Language & Help';bl_idname='SIMPLEBAKE_MT_language_menu'
	def draw(B,context):
		A=B.layout;C=bpy.context.preferences.view.language;D=get_compatible_lang(C)
		if D==_C:A.operator(_E,text=_H,depress=_B);A.operator(_D,text=_F,depress=_A)
		else:A.operator(_E,text=_H,depress=_A);A.operator(_D,text=_F,depress=_B)
		A.separator();A.operator(_J,text='Tip to Support',icon=_O);A.separator();A.operator(_G,text=_P).url=_Q;A.operator(_G,text=_R).url=_S
_original_preferences_draw=_K
_original_menus_draw={}
_original_panels_draw={}
_original_import_operators_draw={}
_original_export_operators_draw={}
_recursion_protection={}
_is_registered=_B
target_main_menus=[]
if ENABLE_MENU_MODULE and'':target_main_menus=[A.strip()for A in''.split(',')if A.strip()]
main_panel_classes=[]
if ENABLE_PANEL_MODULE and _V:main_panel_classes=[A.strip()for A in _V.split(',')if A.strip()]
def new_preferences_draw(self,context):
	B=self;C=f"prefs_{id(B)}"
	if C in _recursion_protection:silent_print('检测到递归，跳过偏好设置的绘制');return
	_recursion_protection[C]=_A
	try:
		D=B.layout;G=bpy.context.preferences.view.language;E=get_compatible_lang(G)
		if E==_C:D.label(text=_W)
		else:D.label(text='Translation in progress. For suggestions contact B站: 三叔作蜜不甜当醋不酸。')
		H=D.box();A=H.row(align=_A)
		if E==_C:A.operator(_E,text='英文',depress=_B);A.operator(_D,text=_F,depress=_A)
		else:A.operator(_E,text=_H,depress=_A);A.operator(_D,text=_F,depress=_B)
		A.operator(_J,text=_X,icon=_O);A.operator(_G,text=_P).url=_Q;A.operator(_G,text=_R).url=_S;D.separator()
		if _original_preferences_draw and callable(_original_preferences_draw):
			try:F=B.__class__;F.draw=_original_preferences_draw;_original_preferences_draw(B,context)
			except Exception as I:silent_print(f"调用原始偏好设置draw方法失败: {I}")
			finally:F.draw=new_preferences_draw
	finally:
		if C in _recursion_protection:del _recursion_protection[C]
def modify_preferences():
	I='__module__'
	if not ENABLE_PREFERENCES_MODULE:silent_print('偏好设置模块未启用，跳过偏好设置修改');return
	global _original_preferences_draw
	try:
		silent_print('开始修改偏好设置...');H=__package__;silent_print(f"当前包名: {H}");C=list(bpy.types.AddonPreferences.__subclasses__());silent_print(f"找到 {len(C)} 个 AddonPreferences 子类");B=_K;D=''
		for A in C:
			if hasattr(A,_I)and A.bl_idname==H:B=A;D='bl_idname完全匹配';silent_print(f"通过bl_idname完全匹配找到偏好设置类: {A.__name__}");break
		if not B:
			E=_T.lower()
			for A in C:
				if hasattr(A,_I):
					G=A.bl_idname.lower()
					if E in G or E.replace('_',' ')in G or E.replace('_','')in G:B=A;D='bl_idname包含插件名';silent_print(f"通过bl_idname包含插件名找到偏好设置类: {A.__name__} (bl_idname: {A.bl_idname})");break
		if not B:
			J=[_Y,'SIMPLEBAKEAddonPreferences','SimplebakeAddonPreferences']
			for A in C:
				if A.__name__ in J:B=A;D='类名匹配';silent_print(f"通过类名匹配找到偏好设置类: {A.__name__}");break
		if not B:
			E=_T.lower()
			for A in C:
				F=getattr(A,I,'')
				if E in F.lower():B=A;D='模块名匹配';silent_print(f"通过模块名匹配找到偏好设置类: {A.__name__} (模块: {F})");break
		if B and hasattr(B,_L)and callable(getattr(B,_L,_K)):
			if B.__name__ not in _recursion_protection:_original_preferences_draw=B.draw;B.draw=new_preferences_draw;silent_print(f"成功修改偏好设置类: {B.__name__} (匹配方式: {D})")
			else:silent_print(f"偏好设置类 {B.__name__} 已经在递归保护中，跳过")
		elif not B:
			silent_print('未找到 simplebake 偏好设置类');silent_print('可能的原因:');silent_print('1. 插件没有偏好设置类');silent_print('2. 偏好设置类的bl_idname不匹配');silent_print('3. 插件偏好设置类尚未注册');silent_print('4. 插件使用非标准的偏好设置类名');silent_print('\n所有找到的偏好设置类:')
			for(K,A)in enumerate(C,1):F=getattr(A,I,'未知');L=getattr(A,_I,'未知');silent_print(f"  {K}. {A.__name__} (模块: {F}, bl_idname: {L})")
		else:silent_print('偏好设置类没有 draw 方法或 draw 方法不可调用')
	except Exception as M:silent_print(f"修改偏好设置类失败: {M}");import traceback as N;N.print_exc()
def new_panel_draw_factory(panel_class):
	E=panel_class
	def G(self,context):
		B=self;C=f"panel_{id(B)}"
		if C in _recursion_protection:silent_print(f"检测到递归，跳过面板 {B.__class__.__name__} 的绘制");return
		_recursion_protection[C]=_A
		try:
			F=B.layout;silent_print(f"正在为面板 {B.__class__.__name__} 添加语言按钮");F.label(text=_W);A=F.grid_flow(row_major=_A,align=_A,columns=5);H=bpy.context.preferences.view.language;I=get_compatible_lang(H)
			if I==_C:A.operator(_E,text=_H,depress=_B);A.operator(_D,text=_F,depress=_A)
			else:A.operator(_E,text=_H,depress=_A);A.operator(_D,text=_F,depress=_B)
			A.operator(_J,text=_X,icon=_O);A.operator(_G,text=_P).url=_Q;A.operator(_G,text=_R).url=_S;F.separator();D=_original_panels_draw.get(E.__name__)
			if D and callable(D):
				try:E.draw=D;D(B,context)
				except Exception as J:silent_print(f"调用原始draw方法失败: {J}")
				finally:E.draw=G
		finally:
			if C in _recursion_protection:del _recursion_protection[C]
	return G
def modify_panels():
	if not ENABLE_PANEL_MODULE:silent_print('面板模块未启用，跳过面板修改');return
	if not main_panel_classes:silent_print('没有指定主面板类名，跳过面板修改');return
	D=[]
	for B in main_panel_classes:
		try:
			if hasattr(bpy.types,B):
				A=getattr(bpy.types,B)
				if issubclass(A,bpy.types.Panel)and A!=bpy.types.Panel:D.append(A);silent_print(f"找到目标主面板: {A.__name__}")
				else:silent_print(f"类 {B} 不是面板类")
			else:silent_print(f"未找到类: {B}")
		except Exception as C:silent_print(f"处理类 {B} 时出错: {C}")
	for A in D:
		try:
			if hasattr(A,_L)and A.__name__ not in _original_panels_draw and callable(getattr(A,_L,_K)):_original_panels_draw[A.__name__]=A.draw;E=new_panel_draw_factory(A);A.draw=E;silent_print(f"成功修改目标面板: {A.__name__}")
		except Exception as C:silent_print(f"修改面板 {A.__name__} 失败: {C}")
def load_translations():
	O='LC_MESSAGES';N='translations';silent_print('开始加载翻译...');C=os.path.dirname(os.path.realpath(__file__));D=_C;E=get_compatible_lang(D);silent_print(f"模块路径: {C}");silent_print(f"用户语言: {D}, 兼容语言: {E}");A=os.path.join(C,N,E,O)
	if not os.path.exists(A):A=os.path.join(C,N,D,O)
	silent_print(f"翻译目录: {A}")
	if not os.path.exists(A):silent_print(f"翻译目录不存在: {A}");return
	I=[A for A in os.listdir(A)if A.endswith('.mo')];silent_print(f"找到MO文件: {I}")
	for J in I:
		K=os.path.join(A,J)
		try:
			with open(K,'rb')as P:
				Q=gettext.GNUTranslations(P);R=Q._catalog;L={};F={};L[E]=F
				for(B,G)in R.items():
					if isinstance(B,str)and B:
						for S in bpy.app.translations.contexts:
							M=S,B
							if isinstance(G,str)and G:F[M]=G
							else:F[M]=B
				H=f"translation_simplebake_{J}"
				try:bpy.app.translations.unregister(H)
				except:pass
				bpy.app.translations.register(H,L);silent_print(f"已注册翻译字典: {H}")
		except Exception as T:silent_print(f"加载MO文件失败: {K}, 错误: {T}")
def _safe_register_class(cls,name):
	A=name
	try:
		try:bpy.utils.unregister_class(cls)
		except RuntimeError:pass
		bpy.utils.register_class(cls);silent_print(f"成功注册类: {A}");return _A
	except RuntimeError as B:
		if'already registered'in str(B):silent_print(f"类 {A} 已经注册，跳过");return _B
		else:silent_print(f"注册类 {A} 失败: {B}");return _B
def register_core_classes():
	silent_print('注册核心类...');_safe_register_class(SIMPLEBAKE_OT_SetChinese,'SIMPLEBAKE_OT_SetChinese');_safe_register_class(SIMPLEBAKE_OT_SetEnglish,'SIMPLEBAKE_OT_SetEnglish');_safe_register_class(SIMPLEBAKE_OT_ShowFundImage,'SIMPLEBAKE_OT_ShowFundImage');_safe_register_class(SIMPLEBAKE_MT_LanguageMenu,'SIMPLEBAKE_MT_LanguageMenu')
	if ENABLE_CREATE_PREFERENCES_MODULE:_safe_register_class(SIMPLEBAKE_AddonPreferences,_Y)
	if ENABLE_TEMPORARY_PANEL_MODULE:_safe_register_class(SIMPLEBAKE_PT_LanguagePanel,_Z)
	silent_print('核心类注册完成')
def delayed_setup():
	silent_print('执行延迟设置...');load_translations()
	if ENABLE_PREFERENCES_MODULE:modify_preferences()
	if ENABLE_MENU_MODULE:modify_menus()
	if ENABLE_PANEL_MODULE:modify_panels()
	if ENABLE_OVERLAY_PANEL_MODULE:modify_overlay_panel()
	if ENABLE_IMPORT_MODULE:modify_import_operators()
	if ENABLE_EXPORT_MODULE:modify_export_operators()
	if ENABLE_TEMPORARY_PANEL_MODULE and not _original_panels_draw and not _original_import_operators_draw and not _original_export_operators_draw and hasattr(bpy.types,_Z):silent_print('未找到合适的面板，使用临时面板')
	silent_print('延迟设置完成')
def register_translation():
	global _is_registered
	if _is_registered:silent_print('翻译系统已经注册，跳过重复注册');return
	silent_print('=== 开始注册翻译系统 ===');silent_print(f"当前包名: {__package__}");silent_print(f"目标插件名称: simplebake")
	try:A=bpy.context.preferences.addons[__package__].preferences;silent_print(f"成功访问偏好设置: {A}")
	except Exception as B:silent_print(f"无法访问偏好设置: {B}")
	register_core_classes();bpy.app.timers.register(delayed_setup,first_interval=2.);_is_registered=_A;silent_print('翻译系统注册流程启动')
def unregister_translation():
	global _is_registered;silent_print('开始注销翻译系统...')
	try:bpy.utils.unregister_class(SIMPLEBAKE_OT_SetEnglish)
	except:pass
	try:bpy.utils.unregister_class(SIMPLEBAKE_OT_SetChinese)
	except:pass
	try:bpy.utils.unregister_class(SIMPLEBAKE_OT_ShowFundImage)
	except:pass
	try:bpy.utils.unregister_class(SIMPLEBAKE_MT_LanguageMenu)
	except:pass
	if ENABLE_CREATE_PREFERENCES_MODULE:
		try:bpy.utils.unregister_class(SIMPLEBAKE_AddonPreferences)
		except:pass
	if ENABLE_TEMPORARY_PANEL_MODULE:
		try:bpy.utils.unregister_class(SIMPLEBAKE_PT_LanguagePanel)
		except:pass
	global _original_preferences_draw
	if _original_preferences_draw and ENABLE_PREFERENCES_MODULE:
		try:
			for B in bpy.types.AddonPreferences.__subclasses__():
				if hasattr(B,_I):
					H=B.bl_idname.lower();F=_T.lower()
					if F in H or F.replace('_',' ')in H or F.replace('_','')in H or B.bl_idname.lower()==F:B.draw=_original_preferences_draw;silent_print(f"已恢复偏好设置类的原始draw方法: {B.__name__}");break
		except Exception as A:silent_print(f"恢复偏好设置类失败: {A}")
	global _original_menus_draw
	if ENABLE_MENU_MODULE:
		for(I,D)in _original_menus_draw.items():
			try:
				for B in bpy.types.Menu.__subclasses__():
					if hasattr(B,_I)and B.bl_idname==I:B.draw=D;silent_print(f"已恢复菜单 {I} 的原始draw方法");break
			except Exception as A:silent_print(f"恢复菜单 {I} 失败: {A}")
	global _original_panels_draw
	if ENABLE_PANEL_MODULE:
		for(G,D)in _original_panels_draw.items():
			try:
				if hasattr(bpy.types,G):J=getattr(bpy.types,G);J.draw=D;silent_print(f"已恢复面板 {G} 的原始draw方法")
			except Exception as A:silent_print(f"恢复面板 {G} 失败: {A}")
	if ENABLE_OVERLAY_PANEL_MODULE:
		try:
			E='VIEW3D_PT_overlay'
			if hasattr(bpy.types,E)and E in _original_panels_draw:J=getattr(bpy.types,E);J.draw=_original_panels_draw[E];silent_print(f"已恢复叠加层面板 {E} 的原始draw方法")
		except Exception as A:silent_print(f"恢复叠加层面板失败: {A}")
	global _original_import_operators_draw
	if ENABLE_IMPORT_MODULE:
		for(C,D)in _original_import_operators_draw.items():
			try:
				if hasattr(bpy.types,C):K=getattr(bpy.types,C);K.draw=D;silent_print(f"已恢复导入操作符 {C} 的原始draw方法")
			except Exception as A:silent_print(f"恢复导入操作符 {C} 失败: {A}")
	global _original_export_operators_draw
	if ENABLE_EXPORT_MODULE:
		for(C,D)in _original_export_operators_draw.items():
			try:
				if hasattr(bpy.types,C):K=getattr(bpy.types,C);K.draw=D;silent_print(f"已恢复导出操作符 {C} 的原始draw方法")
			except Exception as A:silent_print(f"恢复导出操作符 {C} 失败: {A}")
	_original_menus_draw.clear();_original_panels_draw.clear();_original_import_operators_draw.clear();_original_export_operators_draw.clear();_is_registered=_B;silent_print('翻译系统注销完成')
if not _is_registered:register_translation()