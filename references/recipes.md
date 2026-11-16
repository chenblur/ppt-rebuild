# 原生 PowerPoint 元件示例

在 `scaffold.py` 生成的页模块中调用这些方法。变量 `c` 是 `K.page()` 返回的画布。
下面以 1280 × 720 的假设参考尺寸说明 API，实际项目按自己的参考图测量。

## 原生页眉

```python
c.rect(48, 100, 1184, 3, fill="#377976")
c.text(48, 44, 1184, 48, "示例标题", size=K.Pt(30),
       bold=True, color="#143537", valign="m")
```

## 渐变、投影和文字强调

```python
panel = c.rect(48, 140, 520, 100, fill=["#E7F3F0", "#FFFFFF"],
               line="#A4C4C0", radius=0.10)
c.shadow(panel, blur=3, dist=2, direction=45, alpha=0.2)
c.text(68, 158, 470, 60, ["本周任务：", ("复核输入", {"color": "#9E5027"})],
       size=K.Pt(20), color="#143537", valign="m")
```

## 过程框与箭头

```python
from pptx.enum.shapes import MSO_SHAPE

for x, label in [(48, "登记"), (350, "复核"), (652, "归档")]:
    c.rect(x, 270, 220, 60, fill="#377976")
    c.text(x, 270, 220, 60, label, size=K.Pt(20),
           color="#FFFFFF", align="c", valign="m")

for x in (280, 582):
    c.shape(MSO_SHAPE.RIGHT_ARROW, x, 285, 55, 30,
            fill="#617978", adj=[0.4, 0.5])
```

## 独立图片对象

用自己有权使用的图。默认等比覆盖目标框，完整显示时用 `c.pic_fit()`。

```python
c.pic("assets/example.jpg", 48, 380, 400, 220)
```

只裁取参考图中属于图片本身的区域。标题、表格和说明文字应保留为原生对象。
完成后用 `render.py` 查看实际输出，再调整字距、层级和图框。
