# 第十七批验收记录

## 第十七批层次实例身份与文档操作原生验证

- capture_get_hierarchy正式开放：身份仅限session/revision，occurrenceId为遍历身份，instancePathSegments由父上下文及完整单元位号构成；path/hierarchicalPath为原生字段，允许重复，不推断完整电气连接。
- `.local/hierarchy-identity-v2-20261023/report.json`、`.local/hierarchy-mcp-20261023/report.json`原生及真实stdio均通过：FULLADD 16项=1根+3顶层器件/块+12子单元；两个halfadd实例，U3A/U3B等共享raw path但单元身份独立。分页、重复、新session重新读取、游标绑定、非法参数、关闭及副本篡改拒绝通过；安装源hash不变。
- 初次验收脚本误预期关闭错误为stale_session，实际已有契约session_lost；`.local/hierarchy-identity-20261023/report.json`失败证据保留，未更改生产错误语义。历史raw path issue仅在身份误判范围结案。H01仍partial：根属性、原生空/循环夹具、覆盖属性来源、资源浸泡及原要求待验收；H02完整层次pin-net未实现。
- `.local/document-lifecycle-v2-20261023/report.json`5原生用例通过：新设计、schematic创建/重命名/删除、page删除；均自有副本、完整保存、新进程重开、源hash保持。仍为内部probe，未开放文档CRUD；依赖/非空/根对象删除保护、SaveAs及原完整范围未完成。首轮工作区路径拒绝报告仍保留。
- 实际89工具；230回归229通过、1原文件symlink权限skip。Allegro/PDF范围不变；本批无GUI、安装/真实设计修改、提交或推送。完整34项未结项。

依据本机OrCAD_Capture_TclTk_Extensions.pdf p40–42及DboInstOccurrence类(p623起)，使用GetRootOccurrence/NewChildrenIter/GetPathName/GetHierPathName/GetReferenceDesignator及有效属性遍历。未将字符串路径解释为网络或跨revision持久ID。
