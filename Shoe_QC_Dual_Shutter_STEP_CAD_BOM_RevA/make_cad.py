import cadquery as cq
import os,json,math,zipfile,csv
from pathlib import Path
D=Path('/mnt/data/shoe_qc_work'); (D/'step').mkdir(exist_ok=True)
# Nominal preliminary dimensions, mm
C={'X':800,'Y':520,'Z':560,'wall_t':3,'opening_y':380,'opening_z':310,'opening_zmin':145,'opening_zmax':455,'door_y':430,'door_z':360,'door_t':4,'door_closed_zmin':120,'door_closed_zmax':480,'lift':350,'rail_l':820,'pillar_l':880,'actuator_stroke':350}
def box(dx,dy,dz):return cq.Workplane('XY').box(dx,dy,dz).val()
def cyl_x(radius,length,y,z,x=0):return cq.Solid.makeCylinder(radius,length,cq.Vector(x-length/2,y,z),cq.Vector(1,0,0))
def cyl_z(radius,length,x,y,z=0):return cq.Solid.makeCylinder(radius,length,cq.Vector(x,y,z-length/2),cq.Vector(0,0,1))
def trans(shape,x=0,y=0,z=0):return shape.translate((x,y,z))
def cut_holes_x(shape,points,r=3.2,depth=15):
 for y,z in points:shape=shape.cut(cyl_x(r,depth,y,z))
 return shape
def cut_holes_z(shape,points,r=3.2,depth=15):
 for x,y in points:shape=shape.cut(cyl_z(r,depth,x,y))
 return shape
PARTS={}
def add(pid,title,sh,color,material,dim,notes,qty,fab=True,front=(1,0,0),dims3=None):
 PARTS[pid]={'title':title,'shape':sh,'color':color,'material':material,'dim':dim,'notes':notes,'qty':qty,'fab':fab,'front':front,'dims3':dims3 or []}
# P01..P02 plate parts
base=cut_holes_z(box(800,520,3),[(x,y) for x in [-375,375] for y in [-235,235]],r=3.25)
add('P01','Tấm đáy / BASE PANEL',base,'#a7bacc','Nhôm tấm 5052 / t=3','800 × 520 × 3', ['4 lỗ Ø6.5 tại (X,Y)=(±375,±235).','Dùng mặt phẳng đáy làm datum Z=0.','Bo cạnh và khử ba via trước khi lắp.'],1,front=(0,0,1),dims3=[('X',800),('Y',520),('t',3)])
top=cut_holes_z(box(800,520,3),[(x,y) for x in [-375,375] for y in [-235,235]],r=3.25)
add('P02','Tấm nóc kín / TOP PANEL',top,'#c4d0dc','Nhôm tấm 5052 / t=3','800 × 520 × 3',['4 lỗ Ø6.5 tại (X,Y)=(±375,±235).','Không khoét cửa, không dùng nắp bật.','Lắp kín cố định với gioăng mép.'],1,front=(0,0,1))
# Front/back long walls, 800 long, 554 tall and 3 thick
longwall=box(800,3,554)
longwall=cut_holes_x(longwall,[],3)
# holes pass through y at x±360,z±245
for x in [-360,0,360]:
 for z in [-245,245]:
  h=cq.Solid.makeCylinder(2.6,12,cq.Vector(x,-6,z),cq.Vector(0,1,0));longwall=longwall.cut(h)
add('P03','Vách trước / sau kín',longwall,'#a4bac9','Nhôm tấm 5052 / t=3','800 × 554 × 3',['2 chi tiết giống nhau cho FRONT và BACK.','6 lỗ Ø5.2, cột X=-360/0/+360, hàng Z=±245.','Vách kín, không cửa, không kính quan sát.'],2,front=(0,-1,0))
# End wall with aperture y ±190, local z=+20 ±155
endwall=box(3,520,554).cut(trans(box(12,380,310),z=20))
endwall=cut_holes_x(endwall,[(y,z) for y in [-240,240] for z in [-236,0,236]],r=2.6)
add('P04','Vách đầu có khẩu độ / END WALL',endwall,'#8eafc5','Nhôm tấm 5052 / t=3','520 × 554 × 3; cutout 380 × 310', ['2 vách đầu X- và X+, đặt đối diện theo cùng trục X.','Khẩu độ: Y=-190...+190; Z tổng thể=145...455.','6 lỗ Ø5.2 tại Y=±240; Z local=-236/0/+236.','Mép dưới khẩu độ cách đáy hộp 145 mm.'],2,front=(1,0,0))
# Door sheet with guide bracket holes
shutter=box(4,430,360)
shutter=cut_holes_x(shutter,[(y,z) for y in [-198,198] for z in [-100,100]],r=3.2)
shutter=cut_holes_x(shutter,[(192,110)],r=4.3)
add('P05','Tấm cửa trượt / SLIDING SHUTTER',shutter,'#f0a34a','Nhôm 5052 / t=4','430 × 360 × 4',['2 tấm giống nhau, đối xứng qua tâm buồng.','4 lỗ Ø6.4 tại Y=±198, Zlocal=±100.','1 lỗ liên kết Ø8.6 tại Y=192, Zlocal=110.','Chồng mép khẩu độ 25 mm mỗi phía khi đóng.','Hành trình nâng đề xuất: +350 mm theo Z.'],2,front=(1,0,0))
# Pillar frame 30x30 hollow 4mm, length880
pillar=box(30,30,880).cut(box(22,22,882))
add('P06','Trụ đỡ ray / RAIL TOWER',pillar,'#7c98ad','Nhôm hộp 30×30×4','30 × 30 × 880',['4 trụ, hai trụ cho mỗi cửa.','Lỗ rỗng giữa 22×22 mm; kết cấu minh họa.','Cần đỡ ray cao hơn nóc hộp khi cửa mở.','Khuyến nghị liên kết cứng bằng thanh giằng nóc P12.'],4,front=(1,0,0))
rail=box(8,12,820)
rail=cut_holes_x(rail,[(0,z) for z in range(-360,361,60)],r=2.2,depth=18)
add('P07','Ray dẫn hướng đứng / LINEAR RAIL',rail,'#247e83','Ray thép, hàng mua tiêu chuẩn','8 × 12 × 820',['4 thanh: 2 ray cho mỗi cửa.','13 lỗ giả định Ø4.4, bước 60, mép đầu 50 mm.','CHỈ là mô hình envelope: thay bằng ray CAD hãng.','Ưu tiên ray + block cùng mã và cùng nhà sản xuất.'],4,False,front=(1,0,0))
# Slider block envelope
block=box(18,28,38)
# channel groove from x negative along rail along z
block=block.cut(trans(box(9,13,40),x=-6))
block=cut_holes_x(block,[(y,z) for y in [-8,8] for z in [-11,11]],r=2.0,depth=25)
add('P08','Con trượt / GUIDE BLOCK',block,'#2b8e94','Block trượt, hàng mua','18 × 28 × 38',['8 block, mỗi ray dùng 2 block.','Rãnh + lỗ chỉ là hình bao minh họa.','Khớp nối block phải tương thích ray P07.','Không gia công block theo các kích thước minh họa.'],8,False,front=(1,0,0))
# L bracket sample
br=box(62,42,5).translate((0,0,-16))
br=br.fuse(trans(box(5,42,32),x=-28.5,z=2.5))
for x in [9,24]:
 for y in [-12,12]:br=br.cut(cyl_z(3.2,12,x,y,-16))
add('P09','Giá chữ L / CARRIAGE BRACKET',br,'#546e87','Thép tấm gấp 5 mm','62 × 42 × 37',['8 cái, ghép block trượt với tấm cửa.','Phôi chấn chữ L: cánh 62, cạnh 42, thành đứng 32, dày 5.','4 lỗ Ø6.4 trên cánh ngang tại X=9,24; Y=±12.','Điều chỉnh offset khi áp vào model ray thực tế.'],8,front=(0,0,1))
# Electric linear actuator: visual purchase envelope
act=box(38,38,290)
act=act.fuse(cq.Solid.makeCylinder(9,18,cq.Vector(0,0,145),cq.Vector(0,0,1)))
add('P10','Thân actuator điện 24 V',act,'#735fa2','Hàng mua / envelope only','38 × 38 × 290; stroke 350',['2 actuator: một bộ nâng mỗi cửa.','Hành trình yêu cầu 350 mm, tải tính theo khối lượng tấm cửa.','Chọn loại có phanh hoặc giải pháp chống tụt khi mất nguồn.','Kích thước body là tham chiếu, KHÔNG phải mã hàng.'],2,False,front=(1,0,0))
rod=cq.Solid.makeCylinder(6,75,cq.Vector(0,0,-37.5),cq.Vector(0,0,1))
add('P10R','Ty actuator (vị trí đóng)',rod,'#b4abc9','Thuộc cụm actuator','Ø12 × 75 lộ thiên (đóng)',['Ty được mô phỏng tại trạng thái cửa đóng.','Khi mở tăng chiều dài lộ thiên +350 mm.','Cần giữ khoảng an toàn và kiểm tra end-stop thực tế.'],2,False,front=(1,0,0))
link=box(48,108,6)
link=cut_holes_z(link,[(0,y) for y in [-42,42]],r=4.2)
add('P11','Tai nối actuator / DRIVE LINK',link,'#c18f52','Thép mạ / t=6','48 × 108 × 6',['2 tai nối, mỗi cửa một cái.','2 lỗ Ø8.4 cách tâm 84 mm theo Y.','Giữ trục truyền lực song song phương Z, tránh xoắn cửa.'],2,front=(0,0,1))
gasket=box(3,20,360)
add('P12','Dải chắn sáng / LIGHT SEAL',gasket,'#434f59','Nỉ/bàn chải chặn sáng / t=3','3 × 20 × 360 (module)',['4 dải đứng + 4 dải ngang cắt theo khẩu độ.','Vật liệu có độ ma sát thấp, không gây kẹt cửa.','Thiết kế mép chồng và kiểm thử độ rò sáng thực tế.'],8,False,front=(1,0,0))
bridge=box(30,500,30)
add('P13','Thanh giằng đỉnh / TOP BRIDGE',bridge,'#819db0','Nhôm hộp 30 × 30','30 × 500 × 30',['2 thanh giằng liên kết 2 trụ cùng một cửa.','Lắp tại Z=875 mm, để ổn định ray vươn cao.','Đây là thanh gá ngoài, không khoét nóc hộp.'],2,front=(0,0,1))
# ASSEMBLY
items=[]
def ins(pid,name,x,y,z,phase='closed'):
 items.append({'pid':pid,'name':name,'loc':(x,y,z),'shape':trans(PARTS[pid]['shape'],x,y,z),'color':PARTS[pid]['color'],'phase':phase})
ins('P01','BASE',0,0,1.5)
ins('P02','ROOF',0,0,558.5)
ins('P03','FRONT_PANEL',0,-258.5,280)
ins('P03','REAR_PANEL',0,258.5,280)
for side,sx in [('L',-1),('R',1)]:
 ins('P04',f'END_{side}',sx*398.5,0,280)
 ins('P05',f'SHUTTER_{side}',sx*407,0,300)
 ins('P13',f'BRIDGE_{side}',sx*430,0,875)
 for yi,sy in [('F',-1),('B',1)]:
  ins('P06',f'TOWER_{side}_{yi}',sx*430,sy*237,440)
  ins('P07',f'RAIL_{side}_{yi}',sx*451,sy*237,450)
  for j,zc in enumerate([205,395],1):
   ins('P08',f'BLOCK_{side}_{yi}_{j}',sx*468,sy*237,zc)
   ins('P09',f'BRACKET_{side}_{yi}_{j}',sx*436,sy*209,zc)
 # actuator offset beyond back row
 ins('P10',f'ACTUATOR_{side}',sx*448,293,200)
 ins('P10R',f'ACT_ROD_{side}',sx*448,293,363+37.5)
 ins('P11',f'DRIVE_LINK_{side}',sx*426,250,420)
 # light seal strips: vertical and horizontal between end panel and shutter
 for yy in [-202,202]:ins('P12',f'SEAL_VERT_{side}_{yy}',sx*403.5,yy,300)
 for zz in [133,467]:
  # different dimension orientation of gasket strip, rotate 90 about X -> spans Y not Z
  s=PARTS['P12']['shape'].rotate((0,0,0),(1,0,0),90)
  items.append({'pid':'P12','name':f'SEAL_H_{side}_{zz}','loc':(sx*403.5,0,zz),'shape':trans(s,sx*403.5,0,zz),'color':'#434f59','phase':'closed'})
# create slide-open assembly with door+2blocks bracket and rod translated +350; pack colors
open_left=[]
for it in items:
 it2=it.copy()
 if it['name'].startswith(('SHUTTER_L','BLOCK_L','BRACKET_L','DRIVE_LINK_L')):
  it2['shape']=trans(it['shape'],z=350)
 # moving rod extends via same shape shift? rod as tip segment shift+350; housing stays
 if it['name']=='ACT_ROD_L':it2['shape']=trans(it['shape'],z=350)
 open_left.append(it2)
# save CAD STEP parts individual
for pid,p in PARTS.items():
 try:cq.exporters.export(p['shape'],str(D/'step'/f'{pid}.step'))
 except Exception as e:print('EXPORT FAILED',pid,e)
# STEP assembly via color/name
from cadquery import Color
try:
 a=cq.Assembly(name='SHOEVISION_QC_DUAL_SHUTTER_REV_A')
 for it in items:
  from matplotlib.colors import to_rgb
  rgb=to_rgb(it['color']); a.add(it['shape'], name=it['name'], color=Color(*rgb))
 a.save(str(D/'step'/'GA_ASSEMBLY_CLOSED.step'))
 print('saved assembly step')
except Exception as e:print('assembly step error',e)
meta={'params':C,'parts':{k:{q:v for q,v in p.items() if q not in ['shape']} for k,p in PARTS.items()},'assembly':[{'pid':a['pid'],'name':a['name'],'loc':a['loc']} for a in items]}
(D/'model_spec.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
with open(D/'BOM.csv','w',encoding='utf-8-sig',newline='') as fp:
 w=csv.writer(fp);w.writerow(['Part','Tên','SL','Kích thước (mm)','Loại','Vật liệu / nhóm'])
 for pid,p in PARTS.items():w.writerow([pid,p['title'],p['qty'],p['dim'],'Gia công' if p['fab'] else 'Mua / tham khảo',p['material']])
print('CREATED PARTS',len(PARTS),'ASSEMBLY ITEMS',len(items),'FILE COUNT',len(list((D/'step').glob('*.step'))))
