# PPT-Rebuild

将已有的 PPT、截图、手机长图或 PDF 页复刻成可编辑的 PowerPoint。逐页沿用参考的构图、文字层级和图片槽位，再换成自己的内容。验收后的页面可按用途和风格归入本地模板库。

- 从原生 PPTX 读取版式，或测量截图中的元素。长图按实际页边界拆分。
- 使用 PowerPoint 原生文本、形状和图表构建。照片作为独立对象插入，保持原比例。
- 缺页先检索本地模板库。只有没有适用参考且用户明确同意指定缺页时，才允许该页用 HTML。
- 渲染后检查断行、图文对齐和旧标识。保留页面映射与来源记录。

## 像素标尺

`grid100.py` 只需 Pillow。它在图片副本上叠加坐标网格，供人或视觉模型读数。它输出 PNG，版式判断和元素测量由读图完成。

```sh
python -m pip install Pillow
python scripts/grid100.py page.png --step 50 --scale 1.6
python scripts/grid100.py page.png --percent 10 -o page_percent.png
python scripts/grid100.py crop.png --origin 38 44 --alpha 0.45
python scripts/grid100.py refs/ -o grids/ --step 100
```

默认刻度为源图像素。用 `--percent` 标相对位置，用 `--origin X Y` 将裁页坐标换回原图。缩放只改变输出尺寸。完整参数见 `python scripts/grid100.py --help`。

## 使用

在支持技能的工具中导入本仓库，调用 `$ppt-rebuild`。也可以直接让工具读取 [SKILL.md](SKILL.md)，然后指定本地参考与新内容。Python 工具可独立使用，无需 API 密钥。

安装 Python 3.10 或更新版本并运行：

```sh
python -m pip install -r requirements.txt
```

以下命令在仓库根目录执行。先把按页排序的本地参考图放到 `PPT-Rebuild-Workbench/inbox/example/`：

```sh
python scripts/scaffold.py --src PPT-Rebuild-Workbench/inbox/example --out PPT-Rebuild-Workbench/work/example --name example
```

用 `scripts/grid100.py` 量取参考图的像素坐标，按 [原生元件示例](references/recipes.md) 填写生成的 `build/p1.py` 等文件。构建并渲染：

```sh
python PPT-Rebuild-Workbench/work/example/build/build.py
python scripts/render.py PPT-Rebuild-Workbench/work/example/out/example.pptx PPT-Rebuild-Workbench/work/example/out/preview
```

渲染可使用 Windows 上的 PowerPoint。LibreOffice 方案需要 `soffice` 和 `pdftoppm` 可从命令行调用。

参考资料、渲染结果与模板库都保存在本地工作台。仓库只提供技能、脚本和手册。按 [模板库手册](references/template-library.md) 创建自己的索引。
