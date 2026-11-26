"""Reproducible illustrative README motion diagrams. No live data or network.
Run with Pillow installed: python render.py PROJECT OUTPUT_DIRECTORY [FONT_DIRECTORY].
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math,sys
P=sys.argv[1]; out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
fontdir=Path(sys.argv[3] if len(sys.argv)>3 else '/system/fonts')
font=next((x for x in [fontdir/'Roboto-Regular.ttf',fontdir/'DejaVuSans.ttf'] if x.exists()),None)
if not font: raise SystemExit('Provide a font directory containing Roboto-Regular.ttf or DejaVuSans.ttf')
W,H=1000,440
BG='#101c2a'; CARD='#1b2b3d'; EDGE='#3d5265'; WHITE='#eff5fb'; MUTED='#a9bfd2'
ACC={'observer':'#71e0d6','weave':'#b5a2ff','forge':'#f0b76e','foundry':'#83d9c6'}[P]
def canvas(title,sub):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 d.rounded_rectangle((1,1,W-2,H-2),radius=22,outline=EDGE,width=2)
 txt(d,32,22,'R H O  /  '+P.upper(),15,ACC)
 txt(d,32,51,title,32,WHITE)
 txt(d,33,93,sub,16,MUTED)
 d.line((32,122,968,122),fill=EDGE,width=1)
 return im,d
def txt(d,x,y,s,n=16,c=WHITE,anchor=None):
 d.text((x,y),s,font=ImageFont.truetype(str(font),n),fill=c,anchor=anchor)
def box(d,x,y,w,h,title,sub='',active=False):
 d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill=CARD,outline=ACC if active else EDGE,width=2)
 txt(d,x+w/2,y+22,title,18,WHITE,'mm')
 if sub:txt(d,x+w/2,y+48,sub,14,MUTED,'mm')
def line(d,a,b,active=False):
 d.line((*a,*b),fill=ACC if active else EDGE,width=3 if active else 2)
def dot(d,x,y,r=5,c=None):
 d.ellipse((x-r,y-r,x+r,y+r),fill=c or ACC)
def pulse(d,a,b,t):
 t=max(0,min(1,t));dot(d,a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,5)
def footer(d,step,description):
 d.line((32,380,968,380),fill=EDGE,width=1)
 txt(d,34,398,step,14,ACC)
 txt(d,185,398,description,14,MUTED)
def observer(i):
 im,d=canvas('Read the network, not a single answer.','Illustrative polling cycle: comparable identities, coverage and evidence.')
 stage=i//12; frac=(i%12)/11
 sources=[(40,152),(40,226),(40,300)]
 for j,(x,y) in enumerate(sources):
  box(d,x,y,184,58,'Endpoint '+chr(65+j),'hash H' if j<2 else ('timeout' if stage>=2 else 'pending'),stage>=1 and j<2)
  line(d,(224,y+29),(390,251),stage>=1 and j<2)
  if stage==0:pulse(d,(224,y+29),(390,251),frac)
  elif stage==1 and j<2:pulse(d,(224,y+29),(390,251),frac)
 box(d,390,203,250,95,'Compare snapshots','network / shard / height / hash',stage>=1)
 line(d,(640,251),(720,251),stage>=2)
 if stage==2:pulse(d,(640,251),(720,251),frac)
 box(d,720,203,240,95,'Agreement' if stage>=2 else 'Evidence report','2 / 3 reachable' if stage>=2 else 'awaiting coverage',stage>=2)
 txt(d,840,322,'READINESS: NOT READY' if stage>=2 else 'Read-only sampling',15,'#f0b76e' if stage>=2 else MUTED,'mm')
 footer(d,['01 / POLL','02 / COMPARE','03 / REPORT','04 / INTERPRET'][stage],['Bounded requests to configured endpoints.','Two endpoints report the same finalized identity.','The third endpoint did not respond.','Agreement is not full coverage or consensus certification.'][stage])
 return im
def weave(i):
 im,d=canvas('A decision tree built from uncertainty.','Illustrative Quantum OS model: one hidden status, several possible realities.')
 stage=i//12;frac=(i%12)/11
 box(d,34,208,190,76,'Unknown','4 possible statuses',True)
 line(d,(224,246),(300,246),stage>=1)
 box(d,300,208,170,76,'Refresh','observe again',stage>=1)
 outcomes=[('Absent / aborted','abort-local'),('Prepared','commit-both'),('Committed','commit-local'),('Retry exhausted','defer')]
 for j,(obs,act) in enumerate(outcomes):
  y=139+j*57
  line(d,(470,246),(553,y+23),stage>=2)
  box(d,553,y,190,48,obs,'',stage>=2)
  line(d,(743,y+23),(785,y+23),stage>=3)
  box(d,785,y,182,48,act,'',stage>=3)
  if stage==2:pulse(d,(470,246),(553,y+23),frac)
 if stage==1:pulse(d,(224,246),(300,246),frac)
 footer(d,['01 / BELIEF','02 / OBSERVE','03 / BRANCH','04 / DECIDE'][stage],['Do not assume that silence means absence.','Refresh is the first allowed action in this model.','Each modeled observation selects a branch.','Reach a recommendation or defer; no settlement is performed.'][stage])
 return im
def forge(i):
 im,d=canvas('Conserve resources. Compose a mission.','Illustrative escrow marking: three funding actions and one reservation.')
 stage=i//8;frac=(i%8)/7
 for x,title,sub in [(55,'Buyer','credit'),(380,'Escrow','credit'),(705,'Reserved','item')]:
  box(d,x,158,240,152,title,sub,stage>=4)
 # The counts move only at completed transition boundaries.
 count=min(stage,3)
 for k in range(3-count):dot(d,115+k*54,264,15,'#f0b76e')
 for k in range(count):dot(d,440+k*54,264,15,'#f0b76e')
 if stage<3:pulse(d,(285,237),(390,237),frac)
 if stage>=4:dot(d,825,264,19,'#f0b76e')
 else:
  d.rounded_rectangle((806,245,844,283),radius=10,outline=EDGE,width=2)
 txt(d,825,330,'reserved' if stage>=4 else 'not reserved',15,ACC if stage>=4 else MUTED,'mm')
 txt(d,500,350,'buyer: open   |   4 primitive steps to 1 atomic update',19,ACC,'mm')
 footer(d,'MISSION / OPEN','Conceptual primitive path; the generated mission commits only its final marking.')
 return im
def foundry(i):
 im,d=canvas('From declared rules to executable contracts.','Illustrative compiler pipeline: constraints, reachable states and generated code.')
 stage=i//12;frac=(i%12)/11
 box(d,34,145,250,220,'Protocol specification','JSON',stage==0)
 for j,s in enumerate(['resources: 3 seats','roles: agent, customer','guarded integer deltas','free + held + sold = 3','goal: sellout']):
  txt(d,52,215+j*26,s,15,WHITE if stage>=0 else MUTED)
 line(d,(284,254),(340,254),stage>=1)
 if stage==1:pulse(d,(284,254),(340,254),frac)
 pts=[(377,253),(450,177),(450,253),(450,329),(535,201),(535,305),(611,253)]
 for a,b in [(0,1),(0,2),(0,3),(1,4),(2,4),(2,5),(3,5),(4,6),(5,6)]:line(d,pts[a],pts[b],stage>=2)
 for j,(x,y) in enumerate(pts):
  dot(d,x,y,12,ACC if stage>=2 else EDGE)
  txt(d,x,y,str(j),12,BG,'mm')
 txt(d,494,151,'Schematic state graph',15,WHITE,'mm')
 line(d,(625,254),(691,254),stage>=3)
 if stage==3:pulse(d,(625,254),(691,254),frac)
 box(d,691,145,274,220,'Generated output','Rholang + machine model',stage>=3)
 for j,s in enumerate(['contract.rho','  private state token','  role capabilities','  version check','machine.json']):
  txt(d,712,215+j*25,s,16,ACC if j in (0,4) else MUTED)
 footer(d,['01 / DECLARE','02 / EXPLORE','03 / CHECK','04 / EMIT'][stage],['Resources, roles, guards, invariants and goals.','Enumerate the reachable finite model.','Reject a reachable violation of a declared invariant.','Generate Rholang and the corresponding machine description.'][stage])
 return im
fn={'observer':observer,'weave':weave,'forge':forge,'foundry':foundry}[P]
frames=[fn(i) for i in range(48)]
# Palette quantization, slow readable motion, no flashing.
frames[0].save(out/'overview.gif',save_all=True,append_images=frames[1:],duration=130,loop=0,optimize=True,disposal=2)
frames[-1].save(out/'overview.png',optimize=True)
with Image.open(out/'overview.gif') as im:assert im.n_frames>20 and im.size==(W,H)
print(P, (out/'overview.gif').stat().st_size, 'bytes')
