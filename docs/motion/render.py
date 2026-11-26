"""Four illustrative motion designs. Python + Pillow; no product dependencies.
python render.py observer|weave|forge|foundry OUTPUT_DIRECTORY [FONT_DIRECTORY]
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys,math
project=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
fontdir=Path(sys.argv[3] if len(sys.argv)>3 else '/system/fonts')
def fontfile(*names):
 for n in names:
  if (fontdir/n).is_file():return str(fontdir/n)
 raise ValueError('Missing font: '+str(names))
SANS=fontfile('Roboto-Regular.ttf','DejaVuSans.ttf')
SERIF=fontfile('NotoSerif-Regular.ttf','DejaVuSerif.ttf','Roboto-Regular.ttf')
MONO=fontfile('DroidSansMono.ttf','DejaVuSansMono.ttf','Roboto-Regular.ttf')
from functools import lru_cache
@lru_cache(None)
def font(n,kind='sans'):return ImageFont.truetype({'sans':SANS,'serif':SERIF,'mono':MONO}[kind],n)
def text(d,x,y,s,n=20,c='#ffffff',anchor=None,kind='sans'):
 d.text((x,y),s,font=font(n,kind),fill=c,anchor=anchor)
def circle(d,x,y,r,fill=None,outline=None,w=1):d.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=outline,width=w)
def line(d,a,b,c,w=2):d.line((*a,*b),fill=c,width=w)
def interpolate(a,b,t):return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
def eased(t):return t*t*(3-2*t)
def obs(i):
 im=Image.new('RGB',(1000,440),'#071b25');d=ImageDraw.Draw(im)
 for x in range(0,1000,32):line(d,(x,0),(x,440),'#0c2631',1)
 for y in range(0,440,32):line(d,(0,y),(1000,y),'#0c2631',1)
 cx,cy=244,230;active='#70f1c6';dim='#225464'
 text(d,32,23,'RHO OBSERVER   /   FIELD NOTES',14,active,kind='mono')
 for r in (45,91,137,181):circle(d,cx,cy,r,outline=dim)
 for angle in range(0,360,45):
  a=math.radians(angle);line(d,(cx,cy),(cx+181*math.cos(a),cy+181*math.sin(a)),dim,1)
 angle=i*7.5-90
 for j in range(16):
  a=math.radians(angle-j*3);col=(18+j,65-j*2,66-j*2)
  line(d,(cx,cy),(cx+180*math.cos(a),cy+180*math.sin(a)),col,3)
 a=math.radians(angle);line(d,(cx,cy),(cx+180*math.cos(a),cy+180*math.sin(a)),active,2)
 pts=[(166,124),(333,184),(273,377)]
 for j,(x,y) in enumerate(pts):
  c=active if j<2 and i>=8+j*6 else '#f2b15d' if j==2 and i>=26 else dim
  circle(d,x,y,9,c);circle(d,x,y,16,outline=c)
  text(d,x,y-26,chr(65+j),18,c,'mm','mono')
 circle(d,cx,cy,7,active)
 line(d,(465,42),(465,401),dim,1)
 text(d,506,45,'Two answers.',40,'#e8f6f1')
 text(d,506,92,'One missing.',40,'#e8f6f1')
 text(d,509,161,'SOURCE       FINALIZED REPORT',14,'#789daa',kind='mono')
 for j,name in enumerate(['A','B','C']):
  y=199+j*43
  state='hash H' if j<2 and i>=8+j*6 else 'timeout' if j==2 and i>=26 else 'waiting'
  c=active if state=='hash H' else '#f2b15d' if state=='timeout' else '#789daa'
  text(d,509,y,name,20,'#d4e3e8',kind='mono');text(d,653,y,state,20,c,kind='mono')
  line(d,(508,y+30),(961,y+30),dim,1)
 if i>=26:
  text(d,509,346,'2 / 3 reachable',25,active)
  text(d,509,382,'Agreement, but not ready.',23,'#f2b15d')
 else:text(d,509,363,'Sampling configured endpoints...',19,'#789daa')
 return im
def weave(i):
 im=Image.new('RGB',(1000,440),'#f5f0e7');d=ImageDraw.Draw(im)
 ink='#22213b';muted='#726c80';violet='#6846c2';pale='#ded5f1'
 text(d,38,23,'RHO WEAVE',15,violet,kind='mono')
 text(d,38,53,'Silence is not an answer.',35,ink,kind='serif')
 text(d,40,105,'One missing response can hide very different situations.',17,muted)
 # Tangled possibilities, then a single observation resolves the branching.
 x0,y0=92,238;x1,y1=300,238
 circle(d,x0,y0,44,'#e7def7');text(d,x0,y0,'?',48,violet,'mm','serif')
 text(d,92,300,'unknown',16,muted,'mm')
 for j in range(4):
  points=[]
  for k in range(31):
   t=k/30;x=x0+44+(x1-x0-44)*t;y=y0+math.sin(t*math.pi)*(j-1.5)*39+math.sin(t*math.pi*2+i*.12+j)*5
   points.append((x,y))
  d.line(points,fill=violet if i<19 else pale,width=2)
 d.rounded_rectangle((300,207,450,269),radius=31,fill=violet if i>=12 else pale)
 text(d,375,238,'REFRESH',19,'#ffffff' if i>=12 else violet,'mm','mono')
 branches=[('Absent / aborted','abort-local'),('Prepared','commit-both'),('Committed','commit-local'),('Timed out','defer')]
 for j,(label,act) in enumerate(branches):
  y=156+j*62
  pts=[(450,238),(486,238),(530,y),(620,y)]
  d.line(pts,fill=violet if i>=20+j*3 else pale,width=3)
  if 20+j*3<=i<30+j*3:
   p=interpolate((486,238),(530,y),min(1,(i-20-j*3)/8));circle(d,*p,5,violet)
  text(d,532,y-25,label,15,ink if i>=20+j*3 else muted)
  d.rounded_rectangle((658,y-19,961,y+23),radius=8,fill='#e5ddf5' if i>=30 else '#eee9df')
  text(d,679,y+2,act if i>=30 else '...',21,violet,'lm','mono')
 text(d,40,408,'A recommendation or an explicit defer. Never an assumed settlement.',17,muted)
 return im
def forge(i):
 im=Image.new('RGB',(1000,440),'#f5e3c9');d=ImageDraw.Draw(im)
 ink='#4a2b22';accent='#b65a24';steel='#7a4c35'
 text(d,34,20,'RHO FORGE',15,accent,kind='mono')
 text(d,34,46,'Nothing appears from nowhere.',34,ink,kind='serif')
 text(d,35,93,'Three credits move; one item is reserved.',18,steel)
 stage=min(i//9,4);frac=eased((i%9)/8)
 # Conveyor with three physical token trays and a reservation latch.
 d.rounded_rectangle((34,154,680,315),radius=20,fill='#e4c8a4',outline='#be906a',width=2)
 d.rounded_rectangle((52,173,292,296),radius=16,fill='#fff3de',outline='#c69b75',width=2)
 d.rounded_rectangle((422,173,662,296),radius=16,fill='#fff3de',outline='#c69b75',width=2)
 text(d,172,196,'BUYER',18,ink,'mm','mono');text(d,542,196,'ESCROW',18,ink,'mm','mono')
 d.rounded_rectangle((291,230,423,261),radius=12,fill='#c79b76')
 for x in range(303,423,21):line(d,(x,235),(x+9,255),'#976849',2)
 for j in range(3):
  start=(108+j*63,246);end=(478+j*63,246)
  t=1 if stage>j else frac if stage==j else 0
  x,y=interpolate(start,end,t)
  circle(d,x,y,23,'#ab4e1d');circle(d,x,y-3,20,'#e8a64c','#99501f',2);text(d,x,y-4,'1',19,ink,'mm','mono')
 d.rounded_rectangle((716,154,963,315),radius=18,fill='#4a2b22')
 text(d,839,184,'ITEM',17,'#f8e2bd','mm','mono')
 lock=stage>=4
 d.rounded_rectangle((790,225,888,283),radius=8,fill='#e8a64c' if lock else '#90664c')
 d.arc((808,201 if lock else 188,870,252 if lock else 239),180,360,fill='#e8a64c' if lock else '#90664c',width=9)
 text(d,839,299,'RESERVED' if lock else 'AVAILABLE',14,'#f8e2bd','mm','mono')
 text(d,38,343,'3 credits. Always.',25,ink,kind='serif')
 text(d,420,344,'open = fund + fund + fund + reserve',17,steel,kind='mono')
 d.rectangle((35,389,965,393),fill='#d5b18b');d.rectangle((35,389,35+930*min(1,i/36),393),fill=accent)
 text(d,35,407,'The illustrated primitive path becomes one internal atomic update.',16,steel)
 return im
def foundry(i):
 im=Image.new('RGB',(1000,440),'#121525');d=ImageDraw.Draw(im)
 white='#ecf2ff';blue='#91b7ff';muted='#8c98b7';green='#9be5b4'
 text(d,30,20,'RHO FOUNDRY',15,blue,kind='mono')
 text(d,30,49,'Write the rules. Get a contract.',33,white)
 d.rounded_rectangle((30,113,430,370),radius=8,fill='#1b2035',outline='#3c4664')
 d.rounded_rectangle((570,113,970,370),radius=8,fill='#1b2035',outline='#3c4664')
 d.rectangle((31,114,429,146),fill='#292f48');d.rectangle((571,114,969,146),fill='#292f48')
 text(d,47,122,'reservation.json',15,blue,kind='mono');text(d,587,122,'contract.rho',15,green,kind='mono')
 left=['3 seats','free + held + sold = 3','agent can hold and buy','goal: all 3 sold']
 right=['private state','role capabilities','expected version check','sellout transition','+ machine.json']
 for j,s in enumerate(left):
  text(d,51,166+j*39,s,20,white if i>=j*5 else '#41495e',kind='mono')
 # Actual finite reservation graph: each pair (held,sold) has free=3-held-sold.
 coords={(h,s):(462+s*25,311-h*43-s*12) for s in range(4) for h in range(4-s)}
 for (h,s),a in coords.items():
  for q in ((h+1,s),(h-1,s),(h-1,s+1)):
   if q in coords:line(d,a,coords[q],blue if i>=20 else '#39445c',1)
 for j,(q,(x,y)) in enumerate(coords.items()):
  circle(d,x,y,4,green if i>=20 and q==(0,3) else blue if i>=20+j else '#39445c')
 text(d,504,337,'10 states',12,muted,'mm','mono')
 for j,s in enumerate(right):
  n=max(0,min(len(s),(i-23-j*3)*3))
  text(d,592,166+j*35,s[:n],19,green if j in (3,4) else white,kind='mono')
 if i>=39:
  text(d,591,340,'Generated from the model.',14,muted)
 text(d,30,396,'3 seats. No fourth seat. The rules become executable.',18,blue)
 return im
fn={'observer':obs,'weave':weave,'forge':forge,'foundry':foundry}[project]
frames=[fn(i) for i in range(48)]
# Keep the last state readable before looping. No rapid flashing.
frames[0].save(out/'overview.gif',save_all=True,append_images=frames[1:],duration=[110]*47+[1800],loop=0,optimize=True,disposal=2)
frames[-1].save(out/'overview.png',optimize=True)
with Image.open(out/'overview.gif') as im:
 assert im.n_frames>20 and im.size==(1000,440)
 print(project,im.n_frames,(out/'overview.gif').stat().st_size)
