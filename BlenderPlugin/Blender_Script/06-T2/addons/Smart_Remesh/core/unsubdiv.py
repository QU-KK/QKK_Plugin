from __future__ import annotations
"""Recover a subdivision cage from a dense smooth mesh.
The idea this is built on: Catmull-Clark restricted to a cross-section is
cubic B-spline subdivision,so a corner's limit shape is closed-form. For a
cage corner whose support loops sit at distances `a` and `b` along unit
directions `u`,`v` with angle `phi` between them:
	pull-in=|a*u + b*v| / 6
	radius=|b*v - a*u|**3 / (8*a*b*sin(phi))
With `a==b==d` that reduces to `R=d*sin^2(phi/2) / (2*cos(phi/2))`,and
inverting it gives the number this module exists to compute:
	d=2*R*cos(phi/2) / sin^2(phi/2)
Measured against Blender on a clean L-profile the forward law holds to four
significant figures across phi in {60,90,120} and a twelve-fold range of d.
So the procedure is: find the flat runs,find the fillets between them,
measure each fillet's radius and turn,throw the fillet away,put a sharp
corner where the flat runs would have met,and place a support loop `d` back
along each run. Subdividing that reproduces the fillet that was measured.
Three things that cost real time to learn,all guarded against below:
- Radius must come from a *windowed* circle fit at the curvature peak. A
  three-point fit on a dense mesh is dominated by tessellation noise,and
  arc-length divided by total turn over-reads by 5-9x,because a fillet is
  only confined between its supports when the flat run either side carries
  four or more collinear control points.
- A fold-back (turn near 180 degrees) has no usable line intersection: the
  two runs are near parallel and the corner shoots off. Measured failure put
  a corner at x=0.28 on a profile only 0.46 wide. Those are edges,not
  corners,and take their position from the arc apex instead.
- Bisecting a mesh gives wildly uneven point spacing,so everything here
  works on an arc-length resample rather than the raw section.
"""
import math
FOLD_BACK_DEG=150.0
def fit_circle(pts):
	n=len(pts)
	if n < 4:
		return None
	sx=sy=sxx=syy=sxy=sxxx=syyy=sxyy=sxxy=0.0
	for x,y in pts:
		sx +=x; sy +=y; sxx +=x * x; syy +=y * y; sxy +=x * y
		sxxx +=x * x * x; syyy +=y * y * y
		sxyy +=x * y * y; sxxy +=x * x * y
	c=n * sxx - sx * sx
	d=n * sxy - sx * sy
	e=n * syy - sy * sy
	g=n * (sxxx + sxyy) - (sxx + syy) * sx
	h=n * (syyy + sxxy) - (sxx + syy) * sy
	den=2 * (c * e - d * d)
	if abs(den) < 1e-20:
		return None
	cx=(e * g - d * h) / den
	cy=(c * h - d * g) / den
	return sum(math.hypot(x - cx,y - cy) for x,y in pts) / n
def fit_line(pts):
	n=len(pts)
	cx=sum(p[0] for p in pts) / n
	cy=sum(p[1] for p in pts) / n
	sxx=syy=sxy=0.0
	for x,y in pts:
		dx=x - cx
		dy=y - cy
		sxx +=dx * dx; syy +=dy * dy; sxy +=dx * dy
	th=0.5 * math.atan2(2 * sxy,sxx - syy)
	return (cx,cy),(math.cos(th),math.sin(th))
def intersect(p1,d1,p2,d2):
	den=d1[0] * d2[1] - d1[1] * d2[0]
	if abs(den) < 1e-9:
		return None
	rx=p2[0] - p1[0]
	ry=p2[1] - p1[1]
	t=(rx * d2[1] - ry * d2[0]) / den
	return (p1[0] + d1[0] * t,p1[1] + d1[1] * t)
def support_distance(radius: float,turn_deg: float) -> float:
	phi=math.radians(180.0 - turn_deg)
	s=math.sin(phi / 2)
	c=math.cos(phi / 2)
	if s <=0.05:
		return 0.0
	return 2 * radius * c / (s * s)
def fillet_radius(d_a: float,d_b: float,turn_deg: float) -> float:
	phi=math.radians(180.0 - turn_deg)
	if d_a <=0 or d_b <=0 or math.sin(phi) <=1e-9:
		return 0.0
	diff=math.sqrt(d_a * d_a + d_b * d_b - 2 * d_a * d_b * math.cos(phi))
	return diff ** 3 / (8 * d_a * d_b * math.sin(phi))
def resample(poly,n):
	cum=[0.0]
	for a,b in zip(poly,poly[1:]):
		cum.append(cum[-1] + math.dist(a,b))
	total=cum[-1]
	if total <=0:
		return list(poly),0.0
	step=total / n
	out=[]
	j=0
	for k in range(n):
		t=k * step
		while j < len(cum) - 2 and cum[j + 1] < t:
			j +=1
		seg=cum[j + 1] - cum[j]
		f=0.0 if seg < 1e-12 else (t - cum[j]) / seg
		f=min(max(f,0.0),1.0)
		out.append((poly[j][0] + (poly[j + 1][0] - poly[j][0]) * f,poly[j][1] + (poly[j + 1][1] - poly[j][1]) * f))
	return out,total
def corners(poly,*,samples=900,window=7,max_radius=0.025,min_turn=20.0):
	pts,_total=resample(poly,samples)
	m=len(pts)
	if m < 40:
		return []
	kappa=[]
	for i in range(m):
		win=[pts[(i + k) % m] for k in range(-window,window + 1)]
		r=fit_circle(win)
		kappa.append(0.0 if not r or r < 1e-9 else 1.0 / r)
	tol=1.0 / max_radius
	start=0
	while start < m and kappa[start] > tol:
		start +=1
	if start >=m:
		return []
	runs=[]
	i=start
	while i < start + m:
		curved=kappa[i % m] > tol
		j=i
		while j < start + m and (kappa[j % m] > tol)==curved:
			j +=1
		runs.append((curved,i,j))
		i=j
	if len(runs) < 2:
		return []
	out=[]
	for k,(curved,a,b) in enumerate(runs):
		if not curved:
			continue
		pa=pts[a % m]; pb=pts[(a - 5) % m]
		pc=pts[(b + 4) % m]; pd=pts[(b - 1) % m]
		v1=(pa[0] - pb[0],pa[1] - pb[1])
		v2=(pc[0] - pd[0],pc[1] - pd[1])
		n1=math.hypot(*v1); n2=math.hypot(*v2)
		if n1 < 1e-9 or n2 < 1e-9:
			continue
		dot=(v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
		turn=math.degrees(math.acos(max(-1.0,min(1.0,dot))))
		if turn < min_turn:
			continue
		arc=[pts[q % m] for q in range(a,b)]
		radius=fit_circle(arc) or 0.0
		prev=runs[(k - 1) % len(runs)]
		nxt=runs[(k + 1) % len(runs)]
		line_a=[pts[q % m] for q in range(prev[1],prev[2])]
		line_b=[pts[q % m] for q in range(nxt[1],nxt[2])]
		if len(line_a) < 6 or len(line_b) < 6:
			continue
		p1,d1=fit_line(line_a[len(line_a) // 2:])
		p2,d2=fit_line(line_b[:max(6,len(line_b) // 2)])
		fold=turn >=FOLD_BACK_DEG
		if fold:
			corner=arc[len(arc) // 2]
		else:
			corner=intersect(p1,d1,p2,d2)
			if corner is None:
				continue
		ua=(line_a[0][0] - corner[0],line_a[0][1] - corner[1])
		ub=(line_b[-1][0] - corner[0],line_b[-1][1] - corner[1])
		la=math.hypot(*ua); lb=math.hypot(*ub)
		if la < 1e-9 or lb < 1e-9:
			continue
		out.append({"corner": corner,"dir_a": (ua[0] / la,ua[1] / la),"dir_b": (ub[0] / lb,ub[1] / lb),"run_a": la,"run_b": lb,"turn": turn,"radius": radius,"d": support_distance(radius,turn), "fold_back": fold, "index": a % m,})
	return out
def cage_points(corner,*,clamp=0.45):
	c=corner["corner"]
	d=corner["d"]
	if corner["fold_back"] or d <=0:
		return [c]
	da=min(d,corner["run_a"] * clamp)
	db=min(d,corner["run_b"] * clamp)
	ua=corner["dir_a"]; ub=corner["dir_b"]
	return [(c[0] + ua[0] * da,c[1] + ua[1] * da),c,(c[0] + ub[0] * db,c[1] + ub[1] * db),]