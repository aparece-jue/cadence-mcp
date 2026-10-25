"""Independent library declarations, with physical and logical maps kept separate."""
def line(a,b):return {'start':a,'end':b,'style':0,'width':0}
def pin(pos,name,kind,start,hot,visible=True):return {'position':pos,'name':name,'pinType':kind,'start':start,'hotSpot':hot,'visible':visible}
def mapping(pos,number,shared=False):return {'position':pos,'number':str(number),'shared':shared,'swapId':0}
def symbol(cell,part,pins):return {'cellName':cell,'partName':part,'pins':pins,'lines':[line([-10,-5],[10,-5]),line([10,-5],[10,5]),line([10,5],[-10,5]),line([-10,5],[-10,-5])]}
def specs():
    resistor={'packageName':'MCP_RES','referenceTemplate':'R?','footprint':'MCP_RES_FP','expectedHomogeneous':True,'symbols':[symbol('RES_CELL','RES.Normal',[pin(0,'A',4,[-10,0],[-20,0]),pin(1,'B',4,[10,0],[20,0])])],'devices':[{'designator':'','position':0,'cellName':'RES_CELL','mapping':[mapping(0,1),mapping(1,2)]}]}
    gate=symbol('GATE_CELL','GATE.Normal',[pin(0,'IN',0,[-10,0],[-20,0]),pin(1,'OUT',2,[10,0],[20,0]),pin(2,'VCC',7,[0,-10],[0,-20],False)])
    homogeneous={'packageName':'MCP_DUAL','referenceTemplate':'U?','footprint':'MCP_DUAL_FP','expectedHomogeneous':True,'symbols':[gate],'devices':[{'designator':d,'position':i,'cellName':'GATE_CELL','mapping':[mapping(0,i*2+1),mapping(1,i*2+2),mapping(2,8,True)]} for i,d in enumerate(('A','B'))]}
    a=symbol('A_CELL','A.Normal',[pin(0,'A',0,[-10,0],[-20,0]),pin(1,'Y',2,[10,0],[20,0]),pin(2,'VCC',7,[0,-10],[0,-20],False)])
    b=symbol('B_CELL','B.Normal',[pin(0,'B',0,[-10,10],[-30,10]),pin(1,'Z',2,[10,10],[30,10]),pin(2,'VCC',7,[0,-10],[0,-30],False)])
    power={'cellName':'POWER_CELL','partName':'POWER.Normal','pins':[pin(0,'VCC',7,[0,-10],[0,-20]),pin(1,'GND',7,[0,10],[0,20])],'lines':[]}
    hetero={'packageName':'MCP_HETERO','referenceTemplate':'U?','footprint':'MCP_HETERO_FP','expectedHomogeneous':False,'symbols':[a,b,power],'devices':[{'designator':'A','position':0,'cellName':'A_CELL','mapping':[mapping(0,1),mapping(1,2),mapping(2,8,True)]},{'designator':'B','position':1,'cellName':'B_CELL','mapping':[mapping(0,3),mapping(1,4),mapping(2,8,True)]},{'designator':'P','position':2,'cellName':'POWER_CELL','mapping':[mapping(0,8,True),mapping(1,7)]}]}
    all_types={'packageName':'MCP_TYPES','referenceTemplate':'J?','footprint':'MCP_TYPES_FP','expectedHomogeneous':True,'symbols':[symbol('TYPE_CELL','TYPE.Normal',[pin(i,'TYPE'+str(i),i,[-10,i*10],[-20,i*10],i%2==0) for i in range(8)])],'devices':[{'designator':'','position':0,'cellName':'TYPE_CELL','mapping':[mapping(i,i+1) for i in range(8)]}]}
    return {'resistor':resistor,'homogeneous_shared':homogeneous,'heterogeneous_power':hetero,'all_pin_types':all_types}
