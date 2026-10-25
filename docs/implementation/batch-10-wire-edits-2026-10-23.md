# 第十批：导线端点修改与删除

2026-10-23。D03/D04仍为部分实现，34项完整验收目标保持active。

## 官方依据与实现

本机Capture Tcl/Tk Extensions PDF p462 Page.DeleteWire、p492 Wire.SetPoint、p511 Alias.SetLocation。新capture_wire_edit.py及固定edit_wire.tcl通过页名、原端点及net唯一定位scalar wire，释放迭代器后操作；不把会话ordinal/native指针持久化为定位依据。只接受两个端点的scalar wire，bus和多点操作未开放。

新增plan/apply/jobs/cancel/recover五个typed工具，实际70。移动需要完整声明附着alias的新坐标，删除需要显式确认附着alias一并删除。目标页全部pin期望必填；其余页保留基线。独立新进程重开比较整份定义/pin-net与连接对象，alias必须仍在owner线上，移动后的owner网名显式核对。仅verified/recovered且hash一致的输出可经固定wire_edit kind再打开。

## 验收

- `.local/wire-edits-5370e67af1/report.json`：水平线及alias向下移动100、另起副本删除导线及alias，两例保存/重开/输出衔接通过；四个目标pin均按事先期望变为未绑定，原文件hash未变。
- `.local/wire-edit-mcp-20261023/report.json`：真实70工具stdio的移动/删除、未确认alias删除拒绝、故意错误pin期望在真实保存后拒绝、失败不重放、pending cancel、jobs分页、严格schema、新服务幂等和已验证输出再开通过。并非覆盖所有原生中断窗口。
- 8项主机测试通过；完整203项回归202通过、1项原文件symlink权限skip。原生Tcl解释器参与回归，原始输出见`.local/regression-203-wire-edit-20261023.txt`。

## 失败后移

`.local/short-via-edit-20261023/report.json`预先声明将两个电阻四脚全部短接，端点改为(290,310)-(530,310)。native保存成功且owned进程剩余0，但独立重开仅两个外侧端点脚绑定，中间脚未绑定，触发wire_edit_net_mismatch。几何覆盖不能证明中间引脚电气连接；未修改oracle或放宽验证。该输出不能作为已验收短接fixture，V01短路反例尚未完成。保留原ISS-V01-short-fixture-open，并新增ISS-D03-interior-pin-topology移队尾。

尚未验收：中间脚/T/交叉/重叠/断点/junction语义矩阵、wire-only网络身份、occurrence、原生DRC、图面、其他器件属性及wire_edit专属真实中断恢复。不能将当前两例作为完整D03通过。下一独立项D05图形与V03原生检查。
