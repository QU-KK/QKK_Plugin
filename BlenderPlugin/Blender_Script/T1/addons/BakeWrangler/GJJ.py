import bpy
def g(s):
	y='★'+s;d={"_":" ","materials":"材质","settings":"设置","material":"材质","bake all":"批量烘焙","samples":"采样","objects":"物体","source":"来源","target":"目标","sample":"采样","output":"输出","Target":"目标","frames":"框架","object":"对象","scene":"场景","image":"图像","color":"颜色","names":"名称","green":"绿色","value":"值","gamma":"伽玛","pass":"通道","mesh":"栅格","pass":"通道","bake":"烘焙","path":"路径","file":"文件","from":"从","blue":"蓝色","red":"红色"," ":""}
	for k,v in d.items():s=s.lower().replace(k,v)
	return s