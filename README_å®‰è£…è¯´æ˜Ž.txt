X1 Despatch Label Generator 安装说明
===================================

这个工具目前是给“X1 Quote Schedule 样式”的 PDF 用的。
导入 X1 Quote Schedule PDF 后，可以导出 Despatch Label PDF。

注意：
- 目前这版是按 X1 Quote Schedule 做的，不是 V6 输入版。
- 如果你的 PDF 排版和现在的 X1 Quote Schedule 差很多，结果可能需要再微调。

一、你电脑上要先装什么
------------------------
1. 安装 Python 3
   到 Python 官网下载安装 Python 3。
   安装时一定要勾选：
   [Add Python to PATH]

二、第一次使用怎么安装
----------------------
1. 把整个这个文件夹放到电脑上，比如桌面。
2. 双击：Install_Dependencies.bat
3. 等它安装完成。
   成功后窗口里一般不会报错。

三、以后怎么使用
----------------
1. 双击：Launch_X1_Despatch_Label.bat
2. 会打开一个小窗口。
3. 选择你的 X1 Quote Schedule PDF。
4. 选择导出的 PDF 保存位置。
5. 点击：Generate Despatch Label
6. 等完成，就会得到导出的 Despatch Label PDF。

四、常见问题
------------
1. 双击 bat 没反应
   - 大概率是 Python 没装好，或者安装时没有勾 Add Python to PATH。

2. 安装依赖时报错
   - 先确认电脑能上网。
   - 再重新双击 Install_Dependencies.bat。

3. 生成失败
   - 检查输入是不是 X1 Quote Schedule 样式 PDF。
   - 检查输出文件是不是正被别的软件打开。

五、以后如果你想做成真正 exe
----------------------------
等这个版本稳定以后，可以再用 PyInstaller 打包成 exe。
目前这个工具已经可以当“小程序”用：
- 先装 Python
- 双击 Launch_X1_Despatch_Label.bat
- 选 PDF
- 导出结果

