# 第五十二批：位图DIB原型与保存失败复核

2026-10-24。未增加公共工具，仍155。生产基线仍两次354回归353通过/1原权限skip；本批只有私有探测和文档变化，未把原型计为公共功能完成，原34项门禁保持。

## 原保存/读取问题

在进程退出信号修正后，用全新私有设计重复原六种保存顺序与预先声明的单wire拓扑。empty通过，其余direct/initial_design/initial_page/save_as/no_page_save仍失败，根退出信号均确认、自有进程0。仅在私有复制的读取器中增加DboState数值，五例均确认3969，文件hash保持；生产inspect.tcl未改。故ISS-D03-new-design-wire-reopen继续open，不能把进程时序修正称为它的修复。旧与新失败都保留。

## 官方依据与实际绑定

本机OrCAD_Capture_TclTk_Extensions.pdf p292的NewBitMap、p710–712的GetBoundingBox/GetLocation/GetBitmapDimension/GetDibSize/GetDib。实际basic绑定有DboTclHelper_sMakeBitMapData(BoundingBox,Location,bmpFile)和sMakeBitmap(struct,graphicObject,page,rotation,state)，已独立验证Part+NULL page创建library vector。实际枚举为BITMAP_VECT=47，GRAPHIC_BITMAP_INST=62。安装自带streamer提到的GetBase64ImageData在本机独立basic绑定不可见，未复制vendor实现。

首轮工厂实际保存后，探测器误用不存在的BITMAP枚举，检查阶段失败，原report false保留。新独立三组2×2/24bpp BMP：原像素、反色像素、先建删临时line再加同图，保存/新进程重开均匹配声明bounds(0,0,20,20)、location(0,0)、dimensions(2,2)、DIB56字节、index13/总14vectors。自建DIB字节在各保存库中恰一份，但文件内搜索本身不作为任意对象图像身份认证。

## 不可使用IsEquivalent认证像素

三个独立加载的库/bitmap对象均不同；原生bitmap IsEquivalent对同图返回1，对仅像素反色也返回1，反向及整个part比较同样1。GetId对这些library vector返回1002，已明确记录不支持，未压掉语义检查。该负例证明不能以几何、DIB长度或IsEquivalent代替像素内容验证。公共bitmap查询/创建/编辑/放置尚未接入，仍应拒绝未知vector，不扩大既有保证。

## 完整DIB读取原型

在自有独立Python进程中嵌入安装自带tcl86.dll，只执行固定仓库Tcl读取脚本，保持DboSession活到字节复制结束。官方GetDib返回本进程的HGLOBAL包装；根据SWIG运行时原生字节序编码及本机8字节值包装，经GlobalSize/GlobalLock逐层验证分配宽度、DIB长度和上限，再复制DIB，关闭锁/会话/解释器。没有任意客户脚本、指针或其他进程内存入口。

先前按普通十六进制或错误包装假设的v1/v2/v3原型均在容量/受控读取检查处失败，未通过，原记录和脚本副本保留；v2受控ReadProcessMemory仅限当前原型进程且返回998。最终路径不再使用该尝试，而用经分配大小验证的GlobalLock。内部表示尚未认证为跨Cadence版本稳定ABI，不据此发布公共接口。

依据：

- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-globallock
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-globalsize
- https://raw.githubusercontent.com/swig/swig/master/Lib/swigrun.swg （PackData按内存字节编码，不是数值地址的普通十六进制写法）

最终独立原型验收：A/B完整56字节DIB分别与事先生成的BMP去掉14字节文件头后的字节完全一致，摘要不同；A对B预期返回失败，实际摘要仍A且源未变。临时移动自己生成的原BMP，在新自有进程仍从OLB读回完整A，之后精确恢复BMP并校验全部源/预期hash。以上验证仅限本批固定私有fixture，尚无公共MCP位图能力。

## 后续实施与验收计划

1. 将私有原型整理为固定adapter白名单的受控嵌入Tcl worker，主服务只传会话/对象与声明，内部句柄不跨进程或进入MCP结果；运行时ABI/长度验证失败须拒绝，配回执丢失/取消/超时/进程信号验收。
2. 增加bitmap descriptor：边界/位置/实际像素尺寸/完整DIB长度和摘要，身份必须包括数据。输入BMP验证、私有复制和指纹绑定，创建后独立重开对照预先声明；其他格式或转换不能凭可显示就计通过。
3. 接入库创建/查询及已建模保留图、替代view比较。保留line-only旧摘要兼容、完整绘制顺序、非目标图形/引脚和模板/属性；修改/替换/删除先核实官方setter和绘制位置能力，不以追加末尾代替保序。
4. 接入source/cache/placed-view校验，至少覆盖同几何不同像素、多个bitmap、源BMP缺失、新进程和故障恢复；新图像、修改图像、仅边界和顺序的负例均须拒错。
5. 完成真实MCP和适当回归后才开放能力。页bitmap instance、标题栏、渲染及其他原范围另验，不将library vector结果代替它们。

原34范围未缩减；本批只提供上述私有证据与后续实施依据。无GUI操作、安装或真实设计修改，无提交推送。机器记录见batch-52-evidence.json。
