# 首版验收记录

验收日期：2026-10-29（Asia/Shanghai）。本机 Windows / Python 3.12.10，openpyxl 3.1.5、defusedxml 0.7.1。

**本机 47 项自动化测试、20 项浏览器流程检查全部通过。** 仅使用人工模拟数据，不代表真实客户准确率或测绘精度合格，也不作为 GitHub 或 Pages 线上验收结论。

| 项目 | 实际结果 |
| --- | --- |
| 正常 CSV / XLSX | 各 12 条记录、0 个问题，与人工清单一致 |
| 异常 CSV / XLSX | 各 12 条记录，11 问题：10 错误、1 提示，涉及 10 条；行号、字段、规则、级别逐项一致 |
| 输入边界 | 空表/未声明坐标系保持待核实；缺表头、多表、损坏文件、超行数拒绝；公式、Excel 错误值和非有限坐标有检查 |
| 原件保留 | 源文件字节/散列保持不变；未自动修改源表 |
| 真实入口 | 实际运行 start.cmd 并打开浏览器；在页面真实选择 CSV 与 XLSX 检查 |
| 导出回读 | 下载 HTML 与 CSV；独立打开 HTML；CSV 的 11 条问题逐项匹配人工预期，HTML 内源文件散列匹配 |
| 模板 | CSV / XLSX 实际下载后与原模板字节一致，XLSX 只有五列表头 |
| 页面状态 | 改配置或换文件清除旧结果；无文件、错误表头、坐标系未声明均明确提示 |
| 展示 | 本地链接可访问；展示页及报告可直接以文件打开；桌面1440px和窄屏390px布局已检查 |
| 一万行模拟输入 | 解析与规则检查通过、0问题；单次本机耗时见验证 JSON，不作为客户性能承诺 |

本地证据：verification/verification.json、test-log.txt、browser-verification.json、download-verification.json、截图及 downloads/ 实际导出。证据不放入公开源码；测试代码、模拟样例与人工预期保留在源码中。

## 本次修正

Excel 错误类型不能冒充正常文本；格式空行不计入非空数据上限；GB18030 CSV 兼容并记录读取编码；空模板和未声明坐标系明确标待核实；展示页明确区分静态样例与本地检查，并提供项目源码、运行说明与 Issue 入口。

## 复核

在项目根目录运行：

```powershell
.venv\Scripts\python.exe scripts\verify.py
.venv\Scripts\python.exe app.py --no-browser --port 8765
```

随后在本地页面选择样例并导出、回读。保留本次浏览器下载文件时，可运行 scripts/verify_downloads.py 重新核对导出物。

## 未验证或待完成

真实客户数据、外业及空间精度、无 Python 的全新电脑安装、客户独立操作及公网质检服务部署未验证。首版源码预览的 [GitHub 仓库](https://github.com/1999Daniel/gis-point-qc)、[Pages 展示页](https://1999daniel.github.io/gis-point-qc/)和 [Issue 入口](https://github.com/1999Daniel/gis-point-qc/issues/new/choose)需在发布后独立核验线上状态，结果另行记录。静态 Pages 不执行上传检查。正式许可证待用户确定；个人主页文案仍为草案，本次不发布到个人主页仓库。
