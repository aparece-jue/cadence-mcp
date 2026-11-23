# 库位图像素替换

`capture_plan_library_vector_edit` 的 update 可使用完整 bitmap replacement。目标必须是该共享视图的最后一个矢量；否则返回 `unsupported_bitmap_draw_position`。新位图会替代旧原生对象，保持序列位置；旧查询身份只属于源库会话。

声明沿用库创建的 `sourceBmp`、独立 `expectedBmpSha256` / `expectedDibSha256`、`expectedDimensions`、`expectedDibSize`、`bounds` 和 `location`。只支持已有严格 BI_RGB24/32 BMP 格式。资产先校验并复制到私有冻结目录，写入前再次校验。多个共享视图和其他现存位图均计入完整 DIB 读取预算。

计划绑定完整源库、全部共享引用和原有图谱。apply 仅修改新 OLB 副本，在所有引用确认后创建新末尾位图并移除旧末尾位图。独立重开核对像素、尺寸、顺序、其他矢量、引脚和模板。用 `capture_open_edited_library(kind="vector")` 打开已验证输出。

仅修改位置/边框仍用 `bitmapGeometry`，保留原像素；不得与 replacement 同时提供。非末尾像素替换、渲染和自动更新 DSN 缓存仍未验收。完成后的产物验证依赖已冻结的预期及输出指纹；不因消耗过的输入 BMP 后续缺失而重放修改。

原生双向位深互换、各视图完整描述、写入前资源篡改拒绝、非法资产、取消及新服务无重放恢复见 [批次166](implementation/batch-166-evidence.json)。
