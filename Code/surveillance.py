#!/usr/bin/env python3

"""
Usage: This is a function script of Liquidity Risk Program
Author: Jingkai Sun
Date: 2021-05-06
Version: 0.03
"""

import time as t
import sys
import numpy as np
import pandas as pd
import ipywidgets as wd
import matplotlib.pyplot as plt
import cx_Oracle as cx
import pymysql as ms
import datetime as dt
from IPython.display import display
from IPython.display import clear_output as clear
from IPython.display import HTML

global yesterday, style
style = {"description_width": "initial"}

def obtain_LastTradingDay(date = str(dt.datetime.today())[0:10]):
    """
    查询上一个交易日

    参数
    ============
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                aa.CAL_DAY \
            FROM \
                (SELECT \
                    CAL_DAY, \
                    cal_flag, \
                    ROW_NUMBER ( ) OVER ( PARTITION BY cal_code ORDER BY cal_day DESC ) AS RN \
                FROM \
                    xrisk.TCALENDAR_DATES \
                WHERE \
                    CAL_CODE = 'CHINA_EX' \
                    AND CAl_FLAG = 1 \
                    AND cal_day between '"+str(pd.to_datetime(date)+dt.timedelta(weeks = -4))[0:10]+"' and '"+date+"') aa \
            WHERE \
                RN = 2"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return pd.to_datetime(data[0][0])

yesterday = obtain_LastTradingDay("2019-12-13")

##################################################################################################################
####################################### (一) 持仓比例监控模块 (A股市场) ############################################
##################################################################################################################

def get_totShare():
    """
    查询所有wind数据库里A股总股本数据
    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')

    cursor = con.cursor()

    sql = "SELECT \
                MAX(b.TOT_SHR), \
                SUBSTR(b.S_INFO_WINDCODE, 1, 6) \
            FROM \
                WIND.ASHARECAPITALIZATION b \
            GROUP BY \
                B.S_INFO_WINDCODE"

    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = [ "totShare", "iCode"]
    df.astype({"totShare": "float", "iCode": "str"})
    return df

def get_fundInfo(date):
    """
    查询所有在给定日期组合产品的信息

    参数
    =====================================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                bb.PORT_NAME, \
                aa.* \
            FROM \
                ( \
                SELECT \
                    a.T_DATE, \
                    a.port_code, \
                    a.i_code, \
                    a.i_name, \
                    a.H_COUNT \
                FROM \
                    xrisk.TCRP_HLD a \
                WHERE \
                    LENGTH( a.acct_code ) = 14 \
                    AND a.a_type = 'SPT_S' \
                ) aa \
                LEFT JOIN XRISK.TPRT_DEFINE bb ON aa.PORT_CODE = bb.port_code \
            WHERE \
                aa.T_DATE = '" + date + "'"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["portName", "tDate", "portCode", "iCode", "iName", "hCount"]
    df["tDate"] = df["tDate"].apply(lambda row: row.replace("-", ""))
    df = df.astype({"hCount": "int"})
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def pct_share(stcdf, funddf, threshold = 4):
    """
    列出持仓占比大于特定比例的组合产品及投资标的

    参数
    ==================================
    stcdf: 万得A股市场数据
    funddf: 组合产品数据
    threshold: 持仓比例阈值
    """

    # Merge two dataframe with same stock code by left method
    df = pd.merge(stcdf, funddf, on = "iCode", how = "inner")

    # Assign column names
    df = df[[ "tDate", "portName",  "portCode",
             "iName", 'iCode', 'hCount', 'totShare']]
    # Obtain first digit of stock code
    df["iniCode"] = df["iCode"].apply(lambda num: num[0])
    # Remove rows with which stock code starts with '4' or '8'
    # "4" "8" means that the stock went public in NEEQ
    df=df[~df['iniCode'].isin(["4", "8"])]
    # Removing stocks in HS Market
    df=df[~df["iCode"].apply(lambda num: len(num)).isin(["5"])]
    # Removing side column
    df = df.iloc[:,0:len(df.columns)-1]
    # Calculating Percentage of the number of share we've held currently
    df['totShare'] = df['totShare'] * 10000
    df['pctShare'] = round((df['hCount']/df['totShare'] * 100),2).apply(lambda row: str(row)+"%")
    # Filter column
    df['pctShare_Tool'] = round((df['hCount']/df['totShare'] * 100),2)
    df = df[df['pctShare_Tool'] >= threshold]
    # Removing side column
    df = df.iloc[:,0:len(df.columns)-1]

    # Giving meaningful names for each column
    df.columns = ["交易日期", "组合名称", "组合代码",
                "股票名称", "股票代码", "持仓股数", "总股本", "持仓占比"]

    # Sort dataframe by rate of return
    df = df.sort_values("持仓占比", ascending=False)
    df.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
    return df

def pct_share_pre(date, threshold = 4):
    """
    筛选匹配所有投资标的日收益率小于给定收益率阈值的组合产品

    参数
    ==========================================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    threshold: 给定收益率阈值
    """

    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    # Convert date into string
    date = str(date)[0:10]

    stcdf = get_totShare()
    funddf = get_fundInfo(date)
    res = pct_share(stcdf, funddf, threshold)
    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def _on_click(sender):
        res.to_csv("../Results/%s_share_percentage.csv" % date.replace("-", ""), encoding="utf_8_sig")
        with out:
            display(HTML("<p><b>保存成功！%s_share_position_ratio.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))
    clear()
    btn.on_click(_on_click)
    out = wd.Output()
    display(btn)
    display(res)
    display(out)

def pct_share_interact():
    """ Position Ratio of Each Fund """
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    threshold = wd.FloatSlider(value = 4, min = 0, max = 20, step = 0.01, description = "监测数值(%)")
    pct_share = wd.interact_manual(pct_share_pre, date = date, threshold = threshold)
    pct_share.widget.children[2].description = "开始查询"
    pct_share.widget.children[2].button_style = "danger"
    display(pct_share)
    return None

##################################################################################################################
#####################################（二）持股数量占20日成交量模块 (A股市场) #######################################
##################################################################################################################

def get_AshareVolume(date):
    """
    查询所有wind数据库里A股成交量数据，
    并返回所有收益率有异常波动并且上市日期大于20天的股票数据
    参数：
    ==========================================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """

    date1 = pd.to_datetime(date)
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    cursor = con.cursor()
    sql = "SELECT \
                aa.Trade_dt, \
                aa.S_info_windcode, \
                aa.S_DQ_VOLUME \
            FROM \
                (SELECT \
                    Trade_dt, \
                    S_info_windcode, \
                    S_DQ_VOLUME, \
                    ROW_NUMBER ( ) OVER ( PARTITION BY S_info_windcode ORDER BY Trade_dt DESC) AS RN  \
                FROM \
                    Wind.AShareEODPrices  \
                WHERE \
                    trade_dt >= '" + str(date1 + dt.timedelta(weeks = -24))[0:10].replace("-", "") + "' \
                    AND trade_dt <= '" + date.replace("-", "") + "') aa \
            WHERE RN <= 20"
    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["tDate", "iCode", "dqVolume"]
    df = df.astype({"dqVolume": "float64"})
    df = df.groupby('iCode').agg({'tDate': 'max', 'dqVolume': 'mean', 'iCode':'count'})
    df.columns = ["tDate", "volume", "count"]
    df = df.reset_index(drop = False)
    df["iCode"] = df["iCode"].apply(lambda x: x[0:6])
    return df

def Amt_OBV20(stcdf, funddf, threshold = 4):
    """
    列出20日成交量占比大于特定数值的组合产品及投资标的

    参数
    =========================
    stcdf: 万得A股市场数据
    funddf: 组合产品数据
    threshold: 比例阈值
    """

    # Merge two dataframe with same stock code by left method
    df = pd.merge(stcdf, funddf, on = ["tDate", "iCode"], how = "outer")

    # Assign column names
    df = df[[ "tDate", "portName",  "portCode",
             "iName", 'iCode', 'hCount', 'volume', 'count']]

    # Obtain first digit of stock code
    df["iniCode"] = df["iCode"].apply(lambda num: num[0])
    # Remove rows with which stock code starts with '4' or '8'
    # "4" "8" means that the stock went public in NEEQ
    df=df[~df['iniCode'].isin(["4", "8"])]
    # Removing stocks in HS Market
    df=df[~df["iCode"].apply(lambda num: len(num)).isin(["5"])]
    # Removing side column
    df = df.iloc[:,0:len(df.columns)-1]
    # Calculating Percentage of the number of share we've held currently
    df['hld/vol'] = round(df['hCount']/df['volume'],2).apply(lambda row: str(row)+"%")
    # Filter column
    df['filterCol'] = round(df['hCount']/df['volume'],2)
    df = df[df['filterCol'] >= threshold]
    # Removing side column
    df = df.iloc[:,0:len(df.columns)-1]

    # Giving meaningful names for each column
    df.columns = ["交易日期", "组合名称", "组合代码",
                "股票名称", "股票代码", "持仓股数", "20日平均成交量", "平均成交量计算天数", "20日平均成交量比例"]

    # Sort dataframe by rate of return
    df = df.sort_values("20日平均成交量比例", ascending=False)
    df.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
    return df

def Amt_OBV20_pre(date = "2020-12-31", threshold = 4):
    """
    可视化展示

    参数
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    threshold: 给定收益率阈值
    """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    # Convert date into string
    date = str(date)[0:10]
    try:
        stcdf = get_AshareVolume(date)
        funddf = get_fundInfo(date)
    except ValueError:
        clear()
        return "没有记录"

    res = Amt_OBV20(stcdf, funddf, threshold)

    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_vol20_pct.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_vol20_pct.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

    btn.on_click(btn_click)
    clear()
    out = wd.Output()
    display(btn)
    display(out)
    display(res)
    return None

def Amt_OBV20_interact():
    """ 20-Day Average OBV of Each Fund """
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    threshold = wd.FloatSlider(value = 200, min = 0, max = 500, step = 1, description = "监测数值(%)")
    vol20 = wd.interact_manual(Amt_OBV20_pre, date = date, threshold = threshold)
    vol20.widget.children[2].description = "开始查询"
    vol20.widget.children[2].button_style = "danger"
    display(vol20)
    return None

##################################################################################################################
####################################### (三) 停牌个股数据（A股市场）################################################
##################################################################################################################

def get_Ashare_suspension(date = "2020-12-31"):
    """
    查询所有wind数据库里A股停复牌信息

    参数：
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"

    输出
    ============================
    当天日期停牌信息（数据框）
    距离查询日期前一个交易日的停牌股票代码（列表）
    """

    date1 = pd.to_datetime(date)
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    cursor = con.cursor()
    LTD = obtain_LastTradingDay(date = date)
    sql = "SELECT \
                S_DQ_SUSPENDDATE, \
                S_INFO_WINDCODE, \
                S_DQ_CHANGEREASON \
            FROM  \
                wind.AShareTradingSuspension \
            WHERE \
                S_DQ_SUSPENDDATE = '"+date.replace("-", "")+"'"

    sql2 = "SELECT \
                S_INFO_WINDCODE \
            FROM  \
                wind.AShareTradingSuspension \
            WHERE \
                S_DQ_SUSPENDDATE = '"+str(LTD)[0:10].replace("-","")+"'"

    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["t_date", "wind_code", "sus_reason"]
    df["wind_code"] = df["wind_code"].apply(lambda x: x[0:6])
    cursor.execute(sql2)
    pre_sus = cursor.fetchall()
    pre_sus = [elem[0] for elem in pre_sus]
    return df, [elem[0:6] for elem in pre_sus]

def get_port_suspension(date = "2020-12-31"):
    """
    查询所有在给定日期组合产品的信息

    参数
    ============
    date: 日期筛选参数 格式为 "yyyy-mm-dd"

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                a.T_DATE, \
                b.PORT_NAME, \
                a.port_code, \
                a.i_name, \
                a.i_code \
            FROM \
                xrisk.TCRP_HLD a, \
                XRISK.TPRT_DEFINE b \
            WHERE \
                a.port_code = b.port_code \
                AND t_date = '"+date+"' \
                AND a.a_type = 'SPT_S'"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["t_date", "port_name", "port_code", "i_name", "i_code"]
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def suspension(stcdf, funddf, preSus_code, pre_sus = False, only_presus = False):
    """
    查询停牌数据

    参数
    =========================
    stcdf: 万得A股市场数据
    funddf: 组合产品数据
    threshold: 持仓比例阈值
    """

    # Merge two dataframe with same stock code by left method
    df = pd.merge(stcdf, funddf, right_on = "i_code", left_on="wind_code", how = "left")
    df = df.dropna()

    # Assign column names
    df = df[[ "t_date_y", "port_name",  "port_code", "i_name", 'wind_code', 'sus_reason']]

    # Giving meaningful names for each column
    df.columns = ["交易日期", "组合名称", "组合代码", "股票名称", "股票代码", "停牌原因"]

    # Sort dataframe by rate of return
    df.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)

    if pre_sus == False:
        return df
    else:
        df["是否新增停牌股票"] = df["股票代码"].apply(lambda x: "NO" if x in preSus_code else "YES")

    if only_presus == True:
        df = df[df["是否新增停牌股票"] == "NO"]

    return df

def suspension_pre(date, pre_sus, only_presus):
    """
    筛选所有当日停牌和与昨日比新增停牌的产品

    参数
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    pre_sus: 是否查看新增停牌情况
    """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    # Convert date into string
    date = str(date)[0:10]
    try:
        stcdf, prelist = get_Ashare_suspension(date)
        funddf = get_port_suspension(date)
    except ValueError:
        clear()
        return "没有记录"

    res = suspension(stcdf, funddf, prelist, pre_sus, only_presus)

    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_suspension.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_suspension.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))
    btn.on_click(btn_click)
    clear()
    out = wd.Output()
    display(btn)
    display(out)
    display(res)
    return None

def sus_interact():
    """ Stock Suspension of Each Fund """
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    pre_sus = wd.Checkbox(value = True, description = '选择是否显示新增停牌情况')
    only_presus = wd.Checkbox(value = False, description = '只看连续停牌股票')
    sus = wd.interact(suspension_pre, date = date, pre_sus = pre_sus, only_presus = only_presus)
    display(sus)
    return None

##########################################################################################################
####################################### (四) 行业集中度查询模块 ############################################
##########################################################################################################

def get_ind_class(indClass = "一级行业分类", ind = ["ALL"], dataPath = "../Data/sw_ind_class.xlsx"):
    """
    查询行业分类信息

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()

    # SQL queries
    sql = """
            SELECT
                a.entry_dt,
                (select s_info_name from wind.ASHAREDESCRIPTION where a.s_info_windcode = s_info_windcode),
                Substr(a.s_info_windcode,1,6),
                a.sw_ind_code,
                Substr(a.sw_ind_code,1,4) ind1_code,
                Substr(a.sw_ind_code,1,6) ind2_code,
                Substr(a.sw_ind_code,1,8) ind3_code
            FROM
                wind.AShareSWIndustriesClass a
            WHERE
                a.cur_sign = 1
        """

    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["eDate", "iName", "iCode", "indCode", "ind1Code", "ind2Code", "ind3Code"]
    indClassName = pd.read_excel(dataPath, dtype = "str")
    df = pd.merge(df, indClassName, on = ["ind1Code", "ind2Code", "ind3Code"], how = "right")
    df["iCode"] = df["iCode"].apply(lambda x: str(x)[0:6])
    if indClass == None:
        df = df[["iName", "iCode", "ind1Name", "ind2Name", "ind3Name"]]
    if indClass == "一级行业分类":
        df = df[["iName", "iCode", "ind1Name"]]
    if indClass == "二级行业分类":
        df = df[["iName", "iCode", "ind2Name"]]
    if indClass == "三级行业分类":
        df = df[["iName", "iCode", "ind3Name"]]

    if indClass != None:
        df.columns = ["iName", "iCode", "indClass"]
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df if ind[0] == "ALL" else df[df["indClass"].isin(ind)]

def get_port_mv(date = "2021-04-05", port = ""):
    """
    查询组合市值和总净值信息

    参数
    ============
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    port：组合代码

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    if port == "":
        sql = "SELECT \
                    a.T_DATE,  \
                    b.PORT_NAME,  \
                    a.port_code,  \
                    a.i_name,  \
                    a.i_code,  \
                    a.H_EVAL,  \
                    (SELECT p_totalnav from xrisk.TCRP_NAV where a.PORT_CODE = PORT_CODE and a.T_DATE = t_date) p_totalnav  \
                FROM  \
                    xrisk.TCRP_HLD a,  \
                    XRISK.TPRT_DEFINE b   \
                WHERE  \
                    a.port_code = b.port_code \
                    AND NOT regexp_like ( a.PORT_CODE, '[A-Z]', 'i' ) \
                    AND a.t_date = '"+date+"'  \
                    AND a.a_type = 'SPT_S'"
    else:
        sql = "SELECT \
                    a.T_DATE, \
                    b.PORT_NAME, \
                    a.port_code, \
                    a.i_name, \
                    a.i_code, \
                    a.H_EVAL, \
                    (SELECT p_totalnav from xrisk.TCRP_NAV where a.PORT_CODE = PORT_CODE and a.T_DATE = t_date) p_totalnav \
                FROM \
                    xrisk.TCRP_HLD a, \
                    XRISK.TPRT_DEFINE b  \
                WHERE \
                    a.port_code = b.port_code  \
                    AND a.port_code = '"+ port +"' \
                    AND t_date = '"+ date +"' \
                    AND a.a_type = 'SPT_S'"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "iCode", "portMV", "portNAV"]
    df = df.astype({"portMV": np.float64, "portNAV": np.float64})
    df["portCode"] = df["portCode"].astype("int")
    # Only returning public offering fund
    df = df[df["portCode"] <= 721000]
    # Filling 0s forward
    df["portCode"] = df["portCode"].apply(lambda x: str(x).zfill(6))
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def module4(stcdf, funddf, threshold = 50):
    """
    查询行业集中度

    参数
    =========================
    stcdf: 万得A股市场数据
    funddf: 组合产品数据
    ind_class: 选取行业分类等级
    """
    df = pd.merge(stcdf, funddf, on = ["iName","iCode"], how = "inner")
    df = df.groupby(["portCode", "indClass"]).agg({"portName": "first", "tDate": "first", "portMV": "sum", "portNAV": "first"})
    df["concentration"] = round(df["portMV"]/df["portNAV"] * 100, 1)
    df = df[df["concentration"] >= threshold]
    df.reset_index(drop = False, inplace = True)
    df = df.sort_values(["portCode", "concentration"], ascending = False)
    df = df[["tDate", "portName", "portCode", "indClass", "portMV", "portNAV", "concentration"]]
    # Giving meaningful names for each column
    df.columns = ["交易日期", "组合名称", "组合代码", "行业分类", "行业市值", "组合总净值", "行业集中度(%)"]
    df = df.sort_values("行业集中度(%)", ascending = False)
    return df.reset_index(drop = True)

def module4_pre(date, ind_class = "一级行业分类", threshold = 50, ind = ["ALL",]):
    """
    查看行业集中度

    参数
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    ind_class: 选取行业分类等级
    """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中(该模块查询稍慢，请耐心等待)...'+'\x1b[0m'+' *****', end='')
    # Convert date into string
    date = str(date)[0:10]
    try:
        stcdf = get_ind_class(indClass = ind_class, ind = ind)
        funddf = get_port_mv(date = date)
    except ValueError:
        clear()
        return "没有记录"

    res = module4(stcdf, funddf, threshold)
    res.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)

    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_industry_concentration.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_industry_concentration.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

    btn.on_click(btn_click)
    out = wd.Output()
    clear()
    display(btn)
    display(out)
    # display(res)
    return res

def module4_idv(date, port = ""):
    """
    查看行业集中度

    参数
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    ind_class: 选取行业分类等级
    """
    if port == "":
        return "请输入组合代码"

    if len(port) == 6:
        print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
        # Convert date into string
        date = str(date)[0:10]
        res = pd.DataFrame(data = None)

        try:
            stcdf = get_ind_class("一级行业分类", ["ALL",])
            funddf = get_port_mv(date = date, port = port)
        except ValueError:
            res1 = None
        else:
            res1 = module4(stcdf, funddf, threshold = 0)
            res1.columns = ["交易日期", "组合名称", "组合代码", "行业名称", "行业市值", "组合总净值", "行业集中度(%)"]

        try:
            stcdf = get_ind_class("二级行业分类", ["ALL",])
            funddf = get_port_mv(date = date, port = port)
        except ValueError:
            res2 = None
        else:
            res2 = module4(stcdf, funddf, threshold = 0)
            res2.columns = ["交易日期", "组合名称", "组合代码", "行业名称", "行业市值", "组合总净值", "行业集中度(%)"]

        try:
            stcdf = get_ind_class("三级行业分类", ["ALL",])
            funddf = get_port_mv(date = date, port = port)
        except ValueError:
            res3 = None
        else:
            res3 = module4(stcdf, funddf, threshold = 0)
            res3.columns = ["交易日期", "组合名称", "组合代码", "行业名称", "行业市值", "组合总净值", "行业集中度(%)"]

        res1["行业分类"] = ["一级行业分类"] * res1.shape[0]
        res2["行业分类"] = ["二级行业分类"] * res2.shape[0]
        res3["行业分类"] = ["三级行业分类"] * res3.shape[0]
        res = res.append(res1)
        res = res.append(res2)
        res = res.append(res3)

        res1.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
        res2.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
        res3.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
        res.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)

        btn = wd.Button(description = "Save To CSV",
                        tooltip = 'Save data into local directory',
                        icon = "angle-double-down",
                        button_style = "info")

        def btn_click(sender):
            res.to_csv("../Results/%s_idv_industry_concentration.csv" % date.replace("-", ""), encoding="utf_8_sig")
            clear()
            with out:
                display(HTML("<p><b>保存成功! %s_idv_industry_concentration.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

        btn.on_click(btn_click)
        clear()
        display(btn)
        out = wd.Output()
        display(out)
        print("\x1b[1;31m" + "|" + ("%s(%s)一级行业行业集中度展示" % (res.index.levels[1][0], res.index.levels[2][0])).center(100,"*") + "|")
        display(res1)
        print("\x1b[1;31m" + "|" + ("%s(%s)二级行业行业集中度展示" % (res.index.levels[1][0], res.index.levels[2][0])).center(100,"*") + "|")
        display(res2)
        print("\x1b[1;31m" + "|" + ("%s(%s)三级行业行业集中度展示" % (res.index.levels[1][0], res.index.levels[2][0])).center(100,"*") + "|")
        display(res3)
        return None
    else:
        return "请输入组合代码"

def module4_interact():
    """ Industiral Concentration of Each Fund """
    ind = get_ind_class(indClass = None, ind = ["ALL"])
    ind1List = list(ind["ind1Name"].unique())
    ind2List = list(ind["ind2Name"].unique())
    ind3List = list(ind["ind3Name"].unique())
    ind1List.insert(0, "ALL")
    ind2List.insert(0, "ALL")
    ind3List.insert(0, "ALL")
    x = wd.Dropdown(value = "一级行业分类",
                            options = ["一级行业分类", "二级行业分类", "三级行业分类"],
                            description = '行业分类')

    def f(x):
        if str(x) == "一级行业分类":
            ind.options = ind1List
            ind_class.value = "一级行业分类"
            ind.value = ["ALL"]
        elif str(x) == "二级行业分类":
            ind.options = ind2List
            ind_class.value = "二级行业分类"
            ind.value = ["ALL"]
        elif str(x) == "三级行业分类":
            ind.options = ind3List
            ind_class.value = "三级行业分类"
            ind.value = ["ALL"]

    date = wd.DatePicker(value = yesterday, description = "选择日期")
    ind_class = wd.Dropdown(value = "一级行业分类",
                            options = ["一级行业分类", "二级行业分类", "三级行业分类"],
                            description = '行业分类',
                            disabled = True)
    threshold = wd.FloatSlider(value = 50, min = 0, max = 100, step = 1, description = "监测数值(%)")
    ind = wd.SelectMultiple(options = ind1List, value = ["ALL"], description = "选择行业")
    port = wd.Text(value = "", placeholder = "输入特定组合代码（6位）", description = "组合代码")
    # ind_class.layout.visibility = 'hidden'
    ind_class.layout.display = 'none'
    threshold.msg_throttle = 1
    ind.msg_throttle = 1

    # print("\x1b[1;31m" + "|" + ("组合行业集中度查询").center(100,"*") + "|")
    int1 = wd.interact(f, x = x)
    int2 = wd.interact_manual(module4_pre, date = date, ind_class = ind_class, threshold = threshold, ind = ind)
#     display(int2.widget.children)
    int2.widget.children[4].description = "开始查询"
    int2.widget.children[4].button_style = "danger"
    display(int1)
    display(int2)

    print("\x1b[1;31m" + "|" + ("单个组合行业集中度查询").center(100,"*") + "|")
    int_idv = wd.interact(module4_idv, date = date, port = port)
    display(int_idv)
    return None

##########################################################################################################
######################################### (五) 投资者结构查询  ############################################
##########################################################################################################

def get_port_hlder(date = "2021-04-05", perc = 0, fdt = 80, ftop1 = 20, ftop10 = 0):
    """
    查询投资者结构数据

    参数
    ============
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    port：需要查询的组合代码
    """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                a.T_DATE, \
                b.PORT_NAME, \
                b.port_code, \
                a.W_P * 100, \
                a.W_F * 100, \
                a.W_TOP1 * 100, \
                a.W_TOP10 * 100 \
            FROM \
                XRISK.TCRP_INVEST_WEIGHT a, \
                XRISK.TPRT_DEFINE b \
            WHERE \
                a.port_code = b.port_code \
                AND a.T_DATE = '"+date+"' \
                AND a.W_P * 100 >= %f \
                AND a.W_F * 100 >= %f \
                AND a.W_TOP1 * 100 >= %f \
                AND a.W_TOP10 * 100 >= %f " % (perc, fdt, ftop1, ftop10)
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "person", "inst", "top1", "top10"]
    df = df.astype({"person":np.float64, "inst":np.float64, "top1":np.float64,"top10": np.float64})
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def module5_pre(date, perc = 0, fdt = 80, ftop1 = 20, ftop10 = 0):
    """
    查看投资者结构

    参数
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    ind_class: 选取行业分类等级
    """
    # Convert date into string
    date = str(date)[0:10]
    try:
        res = get_port_hlder(date, perc, fdt, ftop1, ftop10)
    except ValueError:
        clear()
        return "没有记录"

    res.columns = ["交易日期", "组合名称", "组合代码", "个人投资者占占比", "机构投资者占比", "Top1投资者占比", "Top10投资者占比"]
    res.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_hlder_percentage.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_hlder_percentage.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

    btn.on_click(btn_click)
    clear()
    display(btn)
    out = wd.Output()
    display(out)
    display(res)
    return None

def inv_layout_interact():
    """ Investor Structure of Each Fund """
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    perc = wd.FloatSlider(value = 0, min = 0, max = 100, step = 1, description = "个人投资者(%)", style = style)
    fdt = wd.FloatSlider(value = 80, min = 0, max = 100, step = 1, description = "机构投资者(%)", style = style)
    ftop1 = wd.FloatSlider(value = 20, min = 0, max = 100, step = 1, description = "top1投资者(%)", style = style)
    ftop10 = wd.FloatSlider(value = 0, min = 0, max = 100, step = 1, description = "top10投资者(%)", style = style)
    inv_layout = wd.interact(module5_pre, date = date, perc = perc, fdt = fdt, ftop1 = ftop1, ftop10 = ftop10)
    display(inv_layout)
    return None

############################################################################################################
########################################## (六) 单日可变现能力查询  ##########################################
############################################################################################################

def get_pctNAV_DD(date):
    """
    活期存款可变现能力

    参数
    ===================================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                hld.t_date, \
                (select port_name from xrisk.TPRT_DEFINE where hld.PORT_CODE = port_code) port_name, \
                hld.port_code, \
                hld.i_name, \
                hld.ACCT_CODE, \
                hld.facctattr, \
                hld.h_eval, \
                nav.P_TOTALNAV \
            FROM \
                xrisk.TCRP_HLD hld, xrisk.tcrp_nav nav \
            WHERE \
                hld.PORT_CODE = nav.port_code \
                and hld.t_date = nav.t_date \
                and hld.t_date = '"+date+"' \
                and acct_code like '100201%' \
                and not regexp_like(hld.PORT_CODE, '[A-Z]', 'i')"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "acctCode", "facctattr", "ddMV", "totalNAV"]
    df = df.astype({"ddMV": np.float64, "totalNAV": np.float64})
    df = df[df["portCode"].astype(int) <= 721000]
    df = df.groupby(["portCode"]).agg({"tDate": "first", "portName": "first", "ddMV": "sum", "totalNAV":"first"})
    df["pctNAV_DD"] = round(df["ddMV"] / df["totalNAV"], 4) * 100
    df = df.reset_index(drop = False)
    df = df[["tDate", "portName", "portCode", "pctNAV_DD"]]
    df["tDate"] = df["tDate"].apply(lambda x: x.replace("-", ""))
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def get_pctNAV_IRD(date):
    """
    利率债可变现能力

    参数
    ===========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    all_likes = ['110311', '110320', '110331', '110340', '110351', '110355', '110369']
    for elem in all_likes:
        sql3 = "INSERT INTO all_likes values (%s)" % elem
        cursor.execute(sql3)
    sql = "SELECT \
                hld.t_date, \
                ( SELECT port_name FROM xrisk.TPRT_DEFINE WHERE hld.PORT_CODE = port_code ) port_name, \
                hld.port_code, \
                hld.I_NAME, \
                hld.ACCT_CODE, \
                hld.facctattr, \
                hld.h_eval, \
                nav.P_TOTALNAV \
            FROM \
                xrisk.TCRP_HLD hld, \
                xrisk.tcrp_nav nav  \
            WHERE \
                hld.PORT_CODE = nav.port_code \
                AND hld.t_date = nav.t_date \
                AND hld.t_date = '"+date+"' \
                AND EXISTS ( SELECT 1 FROM all_likes c WHERE hld.acct_code LIKE c.likes || '%' ) \
                and not regexp_like(hld.PORT_CODE, '[A-Z]', 'i')"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "acctCode", "facctattr", "IRDMV", "totalNAV"]
    df = df.astype({"IRDMV": np.float64, "totalNAV": np.float64})
    df = df[df["portCode"].astype(int) <= 721000]
    df = df.groupby(["portCode"]).agg({"tDate": "first", "portName": "first", "IRDMV": "sum", "totalNAV":"first"})
    df["pctNAV_IRD"] = round(df["IRDMV"] / df["totalNAV"], 4) * 100
    df = df.reset_index(drop = False)
    df = df[["tDate", "portName", "portCode", "pctNAV_IRD"]]
    df["tDate"] = df["tDate"].apply(lambda x: x.replace("-", ""))
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def get_wind_volume(date):
    """
    查询所有wind数据库里A股成交量数据，
    并返回所有收益率有异常波动并且上市日期大于20天的股票数据
    参数：
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """

    date1 = pd.to_datetime(date)
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    cursor = con.cursor()
    sql = "SELECT \
                aa.Trade_dt, \
                aa.S_info_windcode, \
                aa.S_DQ_VOLUME, \
                aa.S_DQ_CLOSE \
            FROM \
                (SELECT \
                    Trade_dt, \
                    S_info_windcode, \
                    S_DQ_VOLUME, \
                    S_DQ_CLOSE, \
                    ROW_NUMBER ( ) OVER ( PARTITION BY S_info_windcode ORDER BY Trade_dt DESC) AS RN  \
                FROM \
                    Wind.AShareEODPrices  \
                WHERE \
                    trade_dt BETWEEN '" + str(date1 + dt.timedelta(weeks = -24))[0:10].replace("-", "") + "' \
                    AND '" + date.replace("-", "") + "') aa \
            WHERE RN <= 20"
    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["t_date", "wind_code", "dq_volume", "stc_close"]
    df = df.astype({"dq_volume": np.float64, "stc_close": np.float64})
    df["dq_volume"] = df["dq_volume"] * 100 # unit conversion (hands to stocks)
    df = df.groupby('wind_code').agg({'t_date': 'first', 'dq_volume': 'mean', 'wind_code':'count', 'stc_close': "first"})
    df.columns = ["t_date", "volume", "count", "stc_close"]
    df = df.reset_index(drop = False)
    df["wind_code"] = df["wind_code"].apply(lambda x: x[0:6])
    try:
        # get suspended stocks on a given day
        sql2 = "SELECT \
                SUBSTR(S_INFO_WINDCODE, 1, 6) \
            FROM \
                wind.ASHARETRADINGSUSPENSION \
            WHERE \
                S_DQ_SUSPENDDATE = '"+date.replace("-", "")+"'"
        cursor.execute(sql2)
        data2 = cursor.fetchall()
        df2 = pd.DataFrame(data2)
        df2.columns = ["sus_code"]
        df = pd.merge(df, df2, right_on = "sus_code", left_on = 'wind_code', how = "outer")
        df = df[pd.isnull(df["sus_code"])] # removing suspended stocks
    except ValueError:
        pass
    return df[["t_date", "wind_code", "volume", "count", "stc_close"]]

def get_fundstc_mv(date):
    """
    根据给定日期查询组合产品相关信息

    参数
    ============
    date: 日期筛选参数 格式为 "yyyy-mm-dd"

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                a.T_DATE, \
                (select port_name from xrisk.TPRT_DEFINE where a.PORT_CODE = port_code) port_name, \
                a.port_code, \
                a.i_name, \
                a.i_code, \
                a.H_COUNT, \
                (SELECT P_TOTALNAV FROM XRISK.TCRP_NAV WHERE a.PORT_CODE = PORT_CODE AND a.T_DATE = T_DATE) \
            FROM \
                xrisk.TCRP_HLD a \
            WHERE \
                LENGTH( a.acct_code ) = 14  \
                AND a.a_type = 'SPT_S' \
                and a.T_DATE = '"+date+"' \
                and not EXISTS (select c.likes from all_likes1 c where a.acct_code like c.likes || '%') \
                and not regexp_like(a.PORT_CODE, '[A-Z]', 'i')"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "iCode", "hldCount", "totalNAV"]
    df = df.astype({"hldCount": np.float64, "totalNAV": np.float64})
    df = df[df["portCode"].astype(int) <= 721000]
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def get_pctNAV_stc(date):
    """
    得到组合产品股票投资净值比

    参数
    =====================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """
    stcdf = get_wind_volume(date = date)
    funddf = get_fundstc_mv(date = date)
    df = pd.merge(stcdf, funddf, right_on = "iCode", left_on="wind_code", how = "outer")
    df = df.sort_values("portCode")
    df["liquidity"] = df.apply(lambda row: min(row["volume"], row["hldCount"]), axis = 1)
    df["liquidity"] = df["liquidity"] * df["stc_close"]
    df = df.groupby(["portCode"]).agg({"t_date":"first", "portName": "first","liquidity": "sum", "totalNAV": "first"})
    df = df.reset_index(drop = False)
    df["pctNAV_stc"] = round(df["liquidity"]/df["totalNAV"], 4) * 100
    df.columns = ["portCode", "tDate", "portName", "liquidity", "totalNAV", "pctNAV_stc"]
    return df[["tDate", "portName", "portCode", "pctNAV_stc"]]

def port_liquidity1(date):
    """
    得到组合产品单日可变现能力数据

    参数
    =======================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')

    try:
        pctNAV_DD = get_pctNAV_DD(date).sort_values("portCode")
    except ValueError:
        pctNAV_DD = pd.DataFrame(columns = ["tDate", "portName", "portCode", "pctNAV_DD"])
    try:
        pctNAV_IRD = get_pctNAV_IRD(date).sort_values("portCode")
    except ValueError:
        pctNAV_IRD = pd.DataFrame(columns = ["tDate", "portName", "portCode", "pctNAV_IRD"])
    try:
        pctNAV_stc = get_pctNAV_stc(date).sort_values("portCode")
    except ValueError:
        pctNAV_stc = pd.DataFrame(columns = ["tDate", "portName", "portCode", "pctNAV_stc"])

    df = pd.merge(pctNAV_DD, pctNAV_IRD, on=["tDate", "portName", "portCode"], how = "outer")
    df = pd.merge(df, pctNAV_stc, on=["tDate", "portName", "portCode"], how = "outer")
    df = df[~pd.isna(df["tDate"])]
    df["portName"] = df["portName"].fillna("UNKNOWN")
    df = df.fillna(0)
    if df.shape[0] != 0:
        df["pctNAV"] = df.apply(lambda row: row["pctNAV_DD"] + row["pctNAV_IRD"] + row["pctNAV_stc"], axis = 1)
        df = df[["tDate", "portName", "portCode", "pctNAV_DD", "pctNAV_IRD", "pctNAV_stc", "pctNAV"]]
        df.columns = ["交易日期", "组合名称", "组合代码", "活期存款净值比(%)", "利率债净值比(%)", "股票净值比(%)", "单日可变现能力(%)"]
        df.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
    else:
        pass
    return df

def port_liquidity1_pre(date, threshold = "20"):
    """
    单日可变现能力展示窗口函数

    参数
    ========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    threshold: 监控指标数值，只查看该数值以下的数据
    """
    date = str(date)[0:10]
    res = port_liquidity1(date)
    if res.shape[0] != 0:
        res = res[res["单日可变现能力(%)"] <= threshold]
    else:
        clear()
        return "没有记录"

    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_portLiquidity1.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_portLiquidity1.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))
        return None

    btn.on_click(btn_click)
    clear()
    display(btn)
    out = wd.Output()
    display(out)
    res = res.sort_values("单日可变现能力(%)", ascending = False)
    display(res)
    return None

def liquidity1_interact():
    """ 1-Day Liquidity of Each Fund """
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    threshold = wd.FloatSlider(value = 20, min = 0, max = 200, step = 1,
                               description = "监测数值(%)", tooltip = "单击数值可进行编辑", style = style)
    liqui = wd.interact_manual(port_liquidity1_pre, date = date, threshold = threshold)
    liqui.widget.children[2].description = "开始查询"
    liqui.widget.children[2].button_style = "danger"
    display(liqui)
    return None


############################################################################################################
################################################# 新增ST股票  ###############################################
############################################################################################################

def get_AshareST(date):
    """
    查询所有wind数据库里A股特别处理的股票
    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    cursor = con.cursor()

    sql = "SELECT \
                (select s_info_name from wind.ASHAREDESCRIPTION where a.S_INFO_windCODE = s_info_windcode) stock_name, \
                substr(a.s_info_windcode, 1, 6), \
                a.s_type_st, \
                a.entry_dt, \
                a.remove_dt  \
            FROM \
                wind.asharest a \
            WHERE \
                a.s_type_st = 'S'  \
                AND a.entry_dt = '"+date.replace("-", "")+"'"

    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = [ "iName", "iCode", "stType", "tDate", "rDate"]
    return df

def get_portInfo(date):
    """
    查询所有在给定日期组合产品的信息

    参数
    =====================================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
                a.T_DATE, \
                (select port_name from xrisk.tprt_define where a.port_code = port_code) port_name, \
                a.port_code, \
                a.i_code, \
                a.i_name \
            FROM \
                xrisk.TCRP_HLD a \
            WHERE \
                LENGTH( a.acct_code ) = 14 \
                AND a.a_type = 'SPT_S' \
                and a.T_DATE = '"+date+"'"
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode",
                  "iCode", "iName"]
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def dataProc_ST(date):
    columns = ["交易日期", "组合名称", "组合代码", "股票名称", "股票代码"]
    try:
        ashareST = get_AshareST(date)
        portInfo = get_portInfo(date)
    except:
        return pd.DataFrame(columns = columns)
    portInfo["tDate"] = portInfo["tDate"].apply(lambda row: row.replace("-", ""))
    df = pd.merge(ashareST, portInfo, on = ["tDate","iName","iCode"], how = "inner")
    df = df[["tDate", "portName", "portCode", "iName", "iCode"]]
    df.columns = columns
    return df

def ST_pre(date):
    """
    查询新增ST个股

    参数
    =========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    # Convert date into string
    date = str(date)[0:10]
    res = dataProc_ST(date)

    if len(res["交易日期"]) == 0:
        clear()
        print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'当日无新增ST个股!'+'\x1b[0m'+' *****', end='')
        return None

    res.set_index(["交易日期","组合名称","组合代码"], inplace = True)
    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_ST_new.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功!  %s_ST_new.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))
        return None
    btn.on_click(btn_click)
    clear()
    out = wd.Output()
    display(out)
    display(btn)

    # print("\x1b[1;31m" + "|" + "当日新增ST个股展示".center(80,"*") + "|")
    display(res)
    return None

def ST_interact():
    date = wd.DatePicker(value = yesterday, description = "结束日期")
    st = wd.interact(ST_pre, date = date)
    display(st)
    return None

############################################################################################################
################################################# 股票异常波动情况  #########################################
############################################################################################################

def get_AshareInfo(date, threshold = -9, showAll = False):
    """
    查询所有wind数据库里A股日行情数据，
    并返回所有收益率有异常波动并且上市日期大于20天的股票数据

    参数：
    =========================
    date: 选择查询日期
    threshold: 选择需要监控的收益率(%)

    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    cursor = con.cursor()
    condition = "AND a.S_DQ_PCTCHANGE <=" + str(threshold) if showAll == False else ""
    sql = "SELECT \
                b.S_INFO_NAME, \
                SUBSTR(a.S_INFO_WINDCODE, 1, 6 ), \
                a.TRADE_DT, \
                a.S_DQ_PRECLOSE, \
                a.S_DQ_CLOSE, \
                a.S_DQ_PCTCHANGE, \
                b.S_INFO_LISTDATE \
            FROM \
                wind.ASHAREEODPRICES a, wind.ASHAREDESCRIPTION b \
            WHERE \
                a.S_INFO_WINDCODE = b.S_INFO_WINDCODE \
                AND a.TRADE_DT = '"+date.replace("-", "")+"'" + condition
    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["iName","iCode", "tDate", "preClosePrices", "closePrices", "pctChange", "lDate"]
    df = df.astype({"tDate": "datetime64[ns]", "lDate":"datetime64[ns]", "preClosePrices": np.float64, "closePrices": np.float64, "pctChange": np.float64})
    # Get timedelta from list date to selected date
    df["list_days"] = df["tDate"] - df["lDate"]
    # Convert Timedelta into int format
    df["list_days"] = df["list_days"].dt.days
    df = df[df["list_days"] >= 20]
    df["tDate"] = df["tDate"].apply(lambda row: row.strftime("%F").replace("-",""))
    return df

def get_fundInfo(date, pct_nav = 0.1):
    """
    查询所有在给定日期组合产品的信息

    参数
    ============
    date: 查询日期

    """
    # Create Connection
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    # Create Cursor
    cursor = con.cursor()
    # SQL query
    sql = "SELECT \
            bb.PORT_NAME, \
            aa.*, \
            round( aa.h_eval / aa.p_totalnav, 2 ) \
            FROM \
                ( \
                SELECT \
                    a.T_DATE, \
                    a.port_code, \
                    a.i_code, \
                    a.i_name, \
                    a.H_COUNT, \
                    a.h_eval, \
                    b.P_TOTALNAV \
                FROM \
                    xrisk.TCRP_HLD a, XRISK.TCRP_NAV b \
                WHERE \
                    a.PORT_CODE = b.PORT_CODE \
                    AND a.T_DATE = b.T_DATE \
                    AND LENGTH( a.acct_code ) = 14 \
                    AND a.a_type = 'SPT_S' \
                ) aa \
                LEFT JOIN XRISK.TPRT_DEFINE bb ON aa.PORT_CODE = bb.port_code \
            WHERE \
                aa.T_DATE = '"+date+"' \
                AND round(aa.h_eval / aa.p_totalnav, 2) >=" + str(pct_nav)
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()\
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["portName", "tDate", "portCode", \
                  "iCode", "iName", "hCount", "hPortEval", \
                  "pTotNav", "navRatio"]
    df = df.astype({"hCount": np.float64, "hPortEval": np.float64, "pTotNav": np.float64, "navRatio": np.float64})
    df["tDate"] = df["tDate"].apply(lambda row: row.replace("-", ""))
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

def get_abnomal_voliticity(stcdf, funddf):
    # Merge two dataframe with same stock code by left method
    df = pd.merge(funddf, stcdf, on = ["tDate", "iName", "iCode"], how = "inner")
    # Drop all rows with NAs
#     df = df.dropna()
    # Assign column names
    df = df[[ "tDate", "portName",
             "portCode",  "iName",
             "iCode",'navRatio', 'pctChange']]

    # Giving meaningful names for each column
    df.columns = ["日期", "组合名称",
                "组合代码", "股票名称",
                "股票代码", "净值比例", "收益率"]

    # Sort dataframe by rate of return
    df = df.sort_values("收益率", ascending=True)
    df = df.reset_index(drop = True)
    return df

def abnomal_voliticity_pre(date, threshold = -9.5, pct_nav = 0.1, showAll = False):
    """
    筛选匹配所有投资标的日收益率小于给定收益率阈值的组合产品

    参数
    =========================
    date: 给定日期
    threshold: 给定收益率阈值
    """
    # Convert date into string
    date = str(date)[0:10]

    try:
        ashare_stc = get_AshareInfo(date, threshold, showAll)
        fund_stc = get_fundInfo(date, pct_nav)
    except ValueError:
        return "没有记录"

    res = get_abnomal_voliticity(ashare_stc, fund_stc)
    res.set_index(["日期", "组合名称", "组合代码"], inplace = True)
    btn = wd.Button(description = "Save Data",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_stock_price_abnormal_volatility.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_stock_price_abnormal_volatility.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))
    btn.on_click(btn_click)
    display(btn)
    out = wd.Output()
    display(out)
    display(res)
    return None

def abnormal_voliticity_interact():
    date = wd.DatePicker(value = yesterday, description = "结束日期")
    ror = wd.FloatSlider(value = -9, min = -20, max = 0, step = 0.1, description = "收益率(%)")
    nav_ratio = wd.FloatSlider(value = 0, min = 0, max = 1, step = 0.01, description = "净值比")
    showAll = wd.Checkbox(value = False, description = '查看所有组合')
    wd.interact(abnomal_voliticity_pre, date = date, threshold = ror, pct_nav = nav_ratio, showAll = showAll)
    return None
