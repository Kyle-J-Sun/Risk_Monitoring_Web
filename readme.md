# 风险指标交互式查询网页使用说明

## 程序描述
- 该程序主要用于查询与监控公司所有产品的风险指标情况
- 该程序分为两个网页：
  - **流动性风险监测交互式网页**：该网页主要根据相应的风险指标监测异常产品。
  - **组合风险指标查询程序**： 该网页主要查询产品相对应的风险指标。

## 所需软件：
- [Anaconda3](https://www.anaconda.com/products/individual)
- Oracle 11g 或以上的版本

## 使用方法：
1. 请确保上述列出的所有所需软件已经安装完毕。
2. 解压该程序包到C盘（推荐解压在C盘`文档`文件夹下）。
3. 双击 `Installer.bat` 文件安装所需的插件，并等候所有插件安装完成。
4. 双击 `Launcher.bat` 文件启动该程序。
> 推荐将 `Launcher.bat` 文件创建快捷方式并移动到桌面

## 开发者须知：
1. 请阅读下列程序目录树。
2. 双击 `ForDeveloper` 开发者文件夹。
3. 双击开发者文件夹中的 `Installer_Developer.bat` 文件来安装所有开发所需的插件。
> 在双击 `Installer_Developer.bat` 前，请确保您已安装过 `Installer.bat` 文件中所需的插件。
4. 双击 `Lab_Launcher.bat` 或者 `NB_Launcher.bat` 启动前端开发界面。（区别请见下列程序目录树部分）
> 如果出现闪退情况，请以管理员身份运行 `Lab_Launcher.bat` 或者 `NB_Launcher.bat` 文件。
5. 所有后端python和前端html代码的实现全部存放在 `Code` 文件夹下。（详情见下列程序目录树部分）

## 程序目录树
```bash
│  Installer.bat: # 安装文件，安装所有使用所需的插件。
│  Launcher.bat： # 启动文件，点击启动程序。
│  readme.md： # 说明文档
│
├─Code：# 存储所有该程序所需的后端和前端代码
│
│      lookup.py：# 组合风险指标查询程序的Python实现代码。
│      surveillance.py：# 流动性风险监测程序的Python实现代码。
│      流动性风险监测程序.ipynb：# 流动性风险查询程序的可视化实现（HTML）代码。
│      组合风险指标查询程序.ipynb： # 组合风险指标查询程序的可视化实现（HTML）代码。
│
├─Data：# 存储所有该程序所需的本地数据文件。
│
│      sw_ind_class.xlsx：# 本地数据文件
│
├─ForDeveloper：# 仅供开发者使用
│
│      Installer_Developer.bat：# 安装所有开发者所需的插件
│      Lab_Launcher.bat：# Jupyter Lab启动端
│      NB_Launcher.bat：# Jupyter Notebook启动端
│
├─Results: # 存放所有查询以后需要保存到本地的数据。
└─Sandbox: # 沙箱文件夹，用于存放其他文件。
        Risk_System.md
        Risk_system.pdf
        test_program.ipynb
        流动性.docx
        系统Checklis0312.xlsx
```

