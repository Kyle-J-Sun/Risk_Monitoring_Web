#!/usr/bin/env python3

"""
Usage: This is a function script of Liquidity Risk Program
Author: Jingkai Sun
Date: 2021-05-07
Version: 0.01
 """

import numpy as np
from numpy.lib.function_base import disp
import pandas as pd
import ipywidgets as wd
import matplotlib.pyplot as plt
import cx_Oracle as cx
import pymysql as ms
import datetime as dt
import sys
from IPython.display import display
from IPython.display import clear_output as clear
from IPython.display import HTML

global yesterday, style, Mul_Sel_Layout, Width_Layout
style = {"description_width": "initial"}
Width_Layout = wd.Layout(width = '45%')
Mul_Sel_Layout = wd.Layout(width = '45%', height = '120px')

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
dayBefore = obtain_LastTradingDay(str(yesterday)[0:10])

########################################################（一）可变现能力 #######################################################

def get_port_hlder(date = "2021-04-05"):
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
    sql = """
            SELECT
                a.T_DATE,
                b.PORT_NAME,
                b.port_code,
                a.W_P * 100,
                a.W_F * 100,
                a.W_TOP1 * 100,
                a.W_TOP10 * 100
            FROM
                XRISK.TCRP_INVEST_WEIGHT a,
                XRISK.TPRT_DEFINE b
            WHERE
                a.port_code = b.port_code
                AND a.T_DATE = '{}'
            """.format(date)
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "person", "inst", "top1", "top10"]
    df["tDate"] = df["tDate"].apply(lambda x: x.replace("-", ""))
    df = df.astype({"person":"float", "inst":"float", "top1":"float", "top10":"float"})
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df

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
    sql = """
            SELECT
                hld.t_date,
                (select port_name from xrisk.TPRT_DEFINE where hld.PORT_CODE = port_code) port_name,
                hld.port_code,
                hld.i_name,
                hld.ACCT_CODE,
                hld.facctattr,
                hld.h_eval,
                nav.P_TOTALNAV
            FROM
                xrisk.TCRP_HLD hld, xrisk.tcrp_nav nav
            WHERE
                hld.PORT_CODE = nav.port_code
                AND hld.t_date = nav.t_date
                AND hld.t_date = '{}'
                AND acct_code like '100201%'
                AND NOT regexp_like(hld.PORT_CODE, '[A-Z]', 'i')
                AND NOT regexp_like(hld.port_code, '_', 'i')
        """.format(date)
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "acctCode", "facctattr", "ddMV", "totalNAV"]
    df = df.astype({"ddMV":"float", "totalNAV":"float"})
    df = df[df["portCode"].astype(int) <= 721000]
    df = df.groupby(["portCode"]).agg({"tDate": "first", "portName": "first", "ddMV": "sum", "totalNAV":"first"})
    df["pctNAV_DD"] = round(df["ddMV"] / df["totalNAV"].astype("float"), 4) * 100
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
    sql = """
            SELECT
                hld.t_date,
                ( SELECT port_name FROM xrisk.TPRT_DEFINE WHERE hld.PORT_CODE = port_code ) port_name,
                hld.port_code,
                hld.I_NAME,
                hld.ACCT_CODE,
                hld.facctattr,
                hld.h_eval,
                nav.P_TOTALNAV
            FROM
                xrisk.TCRP_HLD hld,
                xrisk.tcrp_nav nav
            WHERE
                hld.PORT_CODE = nav.port_code
                AND hld.t_date = nav.t_date
                AND hld.t_date = '{}'
                AND EXISTS ( SELECT 1 FROM all_likes c WHERE hld.acct_code LIKE c.likes || '%' )
                AND NOT regexp_like(hld.PORT_CODE, '[A-Z]', 'i')
                AND NOT regexp_like(hld.port_code, '_', 'i')
            """.format(date)
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "acctCode", "facctattr", "IRDMV", "totalNAV"]
    df = df.astype({"IRDMV":"float", "totalNAV":"float"})
    # display(df)
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
    sql = """
            SELECT
                aa.Trade_dt,
                aa.S_info_windcode,
                aa.S_DQ_VOLUME,
                aa.S_DQ_CLOSE
            FROM
                (SELECT
                    Trade_dt,
                    S_info_windcode,
                    S_DQ_VOLUME,
                    S_DQ_CLOSE,
                    ROW_NUMBER ( ) OVER ( PARTITION BY S_info_windcode ORDER BY Trade_dt DESC) AS RN
                FROM
                    Wind.AShareEODPrices
                WHERE
                    trade_dt BETWEEN '%s'
                    AND '%s') aa
            WHERE RN <= 20
            """ % (str(date1 + dt.timedelta(weeks = -24))[0:10].replace("-", ""), date.replace("-", ""))
    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["t_date", "wind_code", "dq_volume", "stc_close"]
    df.dq_volume = df.dq_volume.astype(np.float64)
    df.stc_close = df.stc_close.astype(np.float64)
#     display(df.dtypes)
    df["dq_volume"] = df["dq_volume"] * 100 # unit conversion (hands to stocks)
    df = df.groupby('wind_code').agg({'t_date': 'first', 'dq_volume': 'mean', 'wind_code':'count', 'stc_close': "first"})
    df.columns = ["t_date", "volume", "count", "stc_close"]
    df = df.reset_index(drop = False)
    df["wind_code"] = df["wind_code"].apply(lambda x: x[0:6])
    try:
        # get suspended stocks on a given day
        sql2 = """
                SELECT
                    SUBSTR(S_INFO_WINDCODE, 1, 6)
                FROM
                    wind.ASHARETRADINGSUSPENSION
                WHERE
                    S_DQ_SUSPENDDATE='{}'
                """.format(date.replace("-", ""))
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
    sql = """
            SELECT
                a.T_DATE,
                (select port_name from xrisk.TPRT_DEFINE where a.PORT_CODE = port_code) port_name,
                a.port_code,
                a.i_name,
                a.i_code,
                a.H_COUNT,
                (SELECT P_TOTALNAV FROM XRISK.TCRP_NAV WHERE a.PORT_CODE = PORT_CODE AND a.T_DATE = T_DATE)
            FROM
                xrisk.TCRP_HLD a
            WHERE
                LENGTH( a.acct_code ) = 14
                AND a.a_type = 'SPT_S'
                AND a.T_DATE = '{}'
                AND not regexp_like(a.PORT_CODE, '[A-Z]', 'i')
        """.format(date)
    # and not EXISTS (select c.likes from all_likes1 c where a.acct_code like c.likes || '%')
    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "portName", "portCode", "iName", "iCode", "hldCount", "totalNAV"]
    df = df.astype({"hldCount":"float", "totalNAV":"float"})
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

def port_liquidity1(date, verbose = False):
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
    try:
        invstr_layout = get_port_hlder(date)
    except ValueError:
        invstr_layout = pd.DataFrame(columns = ["tDate", "portName", "portCode", "person", "inst", "top1", "top10"])

    df = pd.merge(pctNAV_DD, pctNAV_IRD, on=["tDate", "portName", "portCode"], how = "outer")
    df = pd.merge(df, pctNAV_stc, on=["tDate", "portName", "portCode"], how = "outer")
    df = pd.merge(df, invstr_layout, on = ["tDate", "portName", "portCode"], how = "outer")
    df = df[~pd.isna(df["tDate"])]
    df["portName"] = df["portName"].fillna("UNKNOWN")
    df[["pctNAV_DD", "pctNAV_IRD", "pctNAV_stc"]] = df[["pctNAV_DD", "pctNAV_IRD", "pctNAV_stc"]].fillna(0)
    if df.shape[0] != 0:
        df["pctNAV"] = df.apply(lambda row: row["pctNAV_DD"] + row["pctNAV_IRD"] + row["pctNAV_stc"], axis = 1)
        if verbose == True:
            df = df[["tDate", "portName", "portCode", "pctNAV_DD", "pctNAV_IRD", "pctNAV_stc",
                     "pctNAV", "person", "inst", "top1", "top10"]]
            df.columns = ["交易日期", "组合名称", "组合代码", "活期存款净值比(%)", "利率债净值比(%)", "股票净值比(%)",
                          "单日可变现能力(%)", "个人投资者占占比(%)", "机构投资者占比(%)", "Top1投资者占比(%)",
                          "Top10投资者占比(%)"]
        else:
            df = df[["tDate", "portName", "portCode", "pctNAV", "person", "inst", "top1", "top10"]]
            df.columns = ["交易日期", "组合名称", "组合代码", "单日可变现能力(%)", "个人投资者占占比(%)",
                          "机构投资者占比(%)", "Top1投资者占比(%)", "Top10投资者占比(%)"]
    else:
        pass
    return df

def port_liquidity1_pre(date, threshold = 20, verbose = False, showAll = False):
    """
    单日可变现能力展示窗口函数

    参数
    ========================
    date: 日期筛选参数 格式为 "yyyy-mm-dd"
    threshold: 监控指标数值，只查看该数值以下的数据
    """
    date = str(date)[0:10]
    res = port_liquidity1(date, verbose)

    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_portLiquidity_investorLayout.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_portLiquidity_investorLayout.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))
        return None

    btn.on_click(btn_click)
    clear()
    display(btn)
    out = wd.Output()
    display(out)
    # display(res)
    res = res.sort_values("单日可变现能力(%)", ascending = True)
    res.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)
    display(res[res["单日可变现能力(%)"] <= threshold]) if showAll == False else display(res)
    return None

def liquidity1_interact():
    """ 1-Day Liquidity of Each Fund """
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    threshold = wd.FloatSlider(value = 20, min = 0, max = 200, step = 1,
                               description = "单日可变现能力监测数值(%)", tooltip = "单击数值可进行编辑", style = style)
    showAll = wd.Checkbox(value = False, description = '查看所有组合')
    verbose = wd.Checkbox(value = False, description = "查看单日可变现能力的具体信息")
    liqui_layout = wd.interact_manual(port_liquidity1_pre, date = date, threshold = threshold, verbose = verbose, showAll = showAll)
    liqui_layout.widget.children[4].description = "开始查询"
    liqui_layout.widget.children[4].button_style = "danger"
    display(liqui_layout)
    return None

##################################################（三）组合净值波动率与最大回撤 ###############################################

def get_portNAV(sDate, eDate, portCode = None):
    """
    查询产品净值

    参数：
    =========================
    sDate: 开始日期
    eDate: 结束日期
    portCode: 组合代码
    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    cursor = con.cursor()

    sql = """
            SELECT
                a.t_date,
                (select port_name from xrisk.TPRT_DEFINE where a.PORT_CODE = port_code) port_name,
                a.port_code,
                a.p_unitnav
            FROM
                xrisk.tcrp_nav a
            WHERE
                a.port_code = '%s'
                AND a.T_DATE BETWEEN '%s' AND '%s'
            """ % (portCode, sDate, eDate)
#     display(sql)
    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)

    try:
        df.columns = ["tDate","pName", "pCode", "pUnitNAV"]
        df = df.astype({"pUnitNAV": "float64"})
    except ValueError:
        return df
    return df.sort_values("tDate", ascending = True)

def get_pInfo(date = None, portList = []):
    """
    查询产品信息

    参数：
    =========================
    date: 查询日期
    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    cursor = con.cursor()

    condition = "AND a.T_DATE = '%s'" % date if date != None else ""
    if len(portList) == 0:
        condition2 = ""
    elif len(portList) == 1:
        condition2 = "AND a.port_code IN {}".format(str(tuple([elem.split("--")[1] for elem in portList])).replace(",", ""))
    else:
        condition2 = "AND a.port_code IN {}".format(str(tuple([elem.split("--")[1] for elem in portList])))
#     display(condition2)
    sql = """
            SELECT Distinct
                (select port_name from xrisk.TPRT_DEFINE where a.PORT_CODE = port_code) port_name,
                a.port_code
            FROM
                xrisk.tcrp_nav a
            WHERE
                NOT regexp_like ( a.PORT_CODE, '[A-Z]', 'i' ) AND NOT regexp_like(PORT_CODE, '_', 'i')
            """ + condition + condition2

    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["pName", "pCode"]
    df["pCode"] = df["pCode"].astype("int")
    df = df[(df["pCode"] <= 721000) & (df["pCode"] != 2957)]
    df["pCode"] = df["pCode"].apply(lambda x: str(x).zfill(6))
    return df.reset_index(drop = True)

def get_indexesReturn(sDate, eDate):
    """
    查询四个指数的收益率
    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'wind', charset = 'utf8')
    cursor = con.cursor()

    sql = """
            SELECT
                trade_dt,
                substr( s_info_windcode, 1, 6 ),
                s_dq_pctchange
            FROM
                wind.AINDEXEODPRICES
            WHERE
                trade_dt BETWEEN '{}' AND '{}'
                AND substr( s_info_windcode, 1, 6 ) IN ( '000688', '399006', '000905', '000300')
            """.format(sDate.replace("-", ""), eDate.replace("-", ""))

    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = [ "tDate", "iCode", "pctChange"]
    df = df.astype({"pctChange": "float64"})
    return df

def get_portReturn(sDate, eDate, pCode):
    """
    查询组合收益率

    参数：
    =========================
    sDate: 开始日期
    eDate: 结束日期
    portCode: 组合代码
    """
    con = ms.connect(host = 'localhost', port = 3306, user = 'root', passwd = 'Kyle9975',
                db = 'xrisk', charset = 'utf8')
    cursor = con.cursor()

    sql = """
            SELECT
                a.t_date,
                (select port_name from xrisk.TPRT_DEFINE where a.PORT_CODE = port_code) port_name,
                a.port_code,
                a.p_unitnav
            FROM
                xrisk.tcrp_nav a
            WHERE
                a.port_code = '{}'
                AND a.T_DATE BETWEEN '{}' AND '{}'
        """.format(pCode, sDate, eDate)

    cursor.execute(sql)
    data = cursor.fetchall()
    df = pd.DataFrame(data)
    df.columns = ["tDate","pName", "pCode", "pUnitNAV"]
    df = df.astype({"pUnitNAV": "float64"})
    df = df.sort_values("tDate", ascending = True)
    df["lagNAV"] = df["pUnitNAV"].shift(1)
    df = df.dropna()
    df.reset_index(drop = True, inplace = True)
    df["return"] = (np.log(df["pUnitNAV"]/df["lagNAV"])) * 100 #计算return
    df["tDate"] = df["tDate"].apply(lambda x: x.replace("-", ""))
    df = df[["tDate", "return"]]
    df.columns = ["tDate", pCode]
    return df

def dataReshape(df, columns = ["hsi300", "kc50", "zz500"]):
    """ 改变指数收益率数据的数据结构 """
    df = df.pivot_table(index = ["tDate"], columns=['iCode'], values= ['pctChange'])
    df.columns = df.columns.droplevel()
    df.columns = columns
    df.reset_index(drop = False, inplace = True)
    return df

def getBeta(*args,df):
    """ 计算单个组合相对其他4个指数的beta值 """
    cov = np.cov(df[list(args)], rowvar = False)
    beta = cov[-1][0:len(args)-1]/cov.diagonal()[0:len(args)-1]
    return beta

def portBeta(pCode, idxReturn, date, duration):
    """ 得到单个组合相对其他4个指数的所有beta值 """
    preDate = str(pd.to_datetime(date) - dt.timedelta(days = np.ceil(duration)))[0:10]
    portReturn = get_portReturn(preDate, date, pCode)
    df = pd.merge(idxReturn, portReturn, on = "tDate", how = "right")
    df = df.dropna()
    betas = list(getBeta("hsi300", "zz500" , "kc50", pCode, df = df))
    return betas

def volatility(pCode, date, duration = 31, verbose = False):
    """ 计算单个组合净值波动率 """
    preDate = str(pd.to_datetime(date) - dt.timedelta(days = np.ceil(duration)))[0:10]
    df = get_portNAV(preDate, date, portCode = pCode)
    if df.shape[0] >= 10:
        # 第一步：计算return
        df["lagNAV"] = df["pUnitNAV"].shift(1) # 滞后列
        df = df.dropna() #去NA
        df.reset_index(drop = True, inplace = True)
        df["return"] = np.log(df["pUnitNAV"]/df["lagNAV"]) #计算return
        # 计算年化波动率
        vola = np.std(df["return"], ddof = 1) * np.sqrt(252)
        if verbose == True:
            return round(vola * 100, 3), df.shape[0], df.at[0,"tDate"]
        else:
            return round(vola * 100, 3)
    else:
        if verbose == True:
            return None, df.shape[0], df.at[0,"tDate"]
        else:
            return None

def maxWithdrawal(pCode, date, duration = 365, verbose = False):
    """ 计算单个组合最大回撤 """
    preDate = str(pd.to_datetime(date) - dt.timedelta(days = np.ceil(duration)))[0:10]
    df = get_portNAV(preDate, date, portCode = pCode)
    df.reset_index(drop = True, inplace = True)
    maxNAV = np.max(df["pUnitNAV"])
    maxWD = (maxNAV - df.at[len(df["pUnitNAV"])-1, "pUnitNAV"])/maxNAV
    if verbose == True:
        return round(maxWD * 100, 3), df.shape[0], df.at[0, "tDate"]
    else:
        return round(maxWD * 100, 3)

def port_VolaWD(date, portList = [], volaDura = 31, maxWDDura = 365, betaDura = 365, verbose = False):
    """ 计算组合净值波动率 """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    date = str(date)[0:10]
    df = get_pInfo(date = date, portList = portList)
    # display(df)
    df["tDate"] = [date] * df.shape[0]
    preDate = str(pd.to_datetime(date) - dt.timedelta(days = np.ceil(betaDura)))[0:10]
    idxReturn = get_indexesReturn(preDate, date)
    idxReturn = dataReshape(idxReturn)

    if verbose == True:
        df["volatility"], df["nVola"], df["sDateVola"] = zip(*df["pCode"].apply(volatility,
                                                                        date = date,
                                                                        duration = volaDura,
                                                                        verbose = verbose))
        df["maxWD"], df["nWD"], df["sDateWD"] = zip(*df["pCode"].apply(maxWithdrawal,
                                                                       date = date,
                                                                       duration = maxWDDura,
                                                                       verbose = verbose))
        df = df[["tDate", "pName", "pCode", "sDateVola",  "volatility", "nVola", "sDateWD", "maxWD", "nWD"]]
        df = df.sort_values(["volatility", "maxWD"], ascending = False)
        df.columns = ["当前查询日期", "组合名称", "组合代码", "净值波动率计算初始日期",
                      "净值波动率(%)", "净值波动率计算天数", "最大回撤计算初始日期", "最大回撤(%)", "最大回撤计算天数"]
    else:
        df["hsi_beta"], df["zz500_beta"], df["kc50_beta"] = zip(*df["pCode"].apply(portBeta,
                                                                               idxReturn = idxReturn,
                                                                               date = date,
                                                                               duration = betaDura))
        df["volatility"] = df["pCode"].apply(volatility,
                                            date = date,
                                            duration = volaDura,
                                            verbose = verbose)

        df["maxWD"] = df["pCode"].apply(maxWithdrawal,
                                           date = date,
                                           duration = maxWDDura,
                                           verbose = verbose)

        df = df[["tDate", "pName", "pCode", "volatility", "maxWD",
                 "hsi_beta", "zz500_beta", "kc50_beta"]]

        df[["hsi_beta", "zz500_beta", "kc50_beta"]] = round(df[["hsi_beta", "zz500_beta", "kc50_beta"]], 3)
        df = df.sort_values(["volatility", "maxWD", "hsi_beta", "zz500_beta", "kc50_beta"], ascending = False)
        df.columns = ["当前查询日期", "组合名称", "组合代码", "净值波动率(%)", "最大回撤(%)",
                      "相对于沪深300指数beta", "相对于中证500指数beta", "相对于科创50指数beta"]

    df.set_index(["当前查询日期","组合名称", "组合代码"], inplace = True)
    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")
    def btn_click(sender):
        df.to_csv("../Results/%s_Volatility_maxWithdrawal_Beta.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_Volatility_maxWithdrawal_Beta.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

    btn.on_click(btn_click)
    clear()
    display(btn)
    out = wd.Output()
    display(out)
    display(df)
    return None

def volaMaxWD_interact():
    pInfo = get_pInfo()
    pInfo = pInfo.sort_values("pCode", ascending = True)
    pInfo['comb'] = pInfo[['pName', 'pCode']].apply(lambda x: '--'.join(x), axis=1)
    date = wd.DatePicker(value = yesterday, description = "结束日期")
    duration = wd.IntSlider(value = 31, min = 5, max = 365, step = 1, description = "净值波动率计算天数", style = style)
    duration2 = wd.IntSlider(value = 365, min = 10, max = 1600, step = 1, description = "最大回撤计算天数", style = style)
    duration3 = wd.IntSlider(value = 365, min = 10, max = 1600, step = 1, description = "beta计算天数", style = style)
    portList = wd.SelectMultiple(options = pInfo["comb"], value = [],
                                 description = "选择特定组合", style = style, layout = Mul_Sel_Layout)

    x = wd.Text(value = '', placeholder = '每个组合代码间以分号分隔',
        description = '请输入组合代码(可多个)：', style = style, layout = Width_Layout)

    def f(x):
        if len(x) == 6:
            clear()
            values = [x]
            portList.value = tuple(pInfo['comb'][pInfo['pCode'].isin(values)])
        elif len(x) > 6:
            clear()
            values = x.replace(" ", "").split(";")
            portList.value = tuple(pInfo['comb'][pInfo['pCode'].isin(values)])
        elif (x != '') and (len(x) < 6):
            display(HTML("<b>请输入至少一个六位的组合代码，或者多个六位的组合代码（用分号分隔）</b>"))
        elif x == '':
            clear()
            portList.value = []


    int1 = wd.interact(f, x = x)
    display(int1)

    verbose = wd.Checkbox(value = False, description = "查看计算初始日期和计算天数")
    volaWDBeta = wd.interact_manual(port_VolaWD, date = date, volaDura = duration,
                         maxWDDura = duration2, betaDura = duration3, portList = portList, verbose = verbose)
    volaWDBeta.widget.children[6].description = "开始查询"
    volaWDBeta.widget.children[6].button_style = "danger"
    display(volaWDBeta)
    return None

################################################################# 组合重仓行业分析 ####################################################

def get_indClass(indClass = None, dataPath = "../Data/sw_ind_class.xlsx"):
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
    if indClass == None or indClass == "":
        df = df[["iName", "iCode", "ind1Name", "ind2Name", "ind3Name"]]
        df.columns = ["iName", "iCode", "indClass1", "indClass2", "indClass3"]
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
    return df

def get_portMV(date = "2021-04-05", portList = []):
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
    sql = """
            SELECT
                a.T_DATE,
                b.PORT_NAME,
                a.port_code,
                a.i_name,
                a.i_code,
                a.H_EVAL,
                (SELECT p_totalnav from xrisk.TCRP_NAV where a.PORT_CODE = PORT_CODE and a.T_DATE = t_date) p_totalnav  \
            FROM
                xrisk.TCRP_HLD a,
                XRISK.TPRT_DEFINE b
            WHERE
                a.port_code = b.port_code
                AND NOT regexp_like ( a.PORT_CODE, '[A-Z]', 'i' )
                AND a.t_date = '{}'
                AND a.a_type = 'SPT_S'
            """.format(date)

    # Execute cursor with given sql query
    cursor.execute(sql)
    # Fetch all records
    data = cursor.fetchall()
    # Convert results into dataframe
    df = pd.DataFrame(data)
    # Assigning name for each column
    df.columns = ["tDate", "pName", "pCode", "iName", "iCode", "pMV", "pTotNAV"]
    df["pCode"] = df["pCode"].astype("int")
    df = df.astype({"pMV": np.float64, "pTotNAV": np.float64})
    # Only returning public offering fund
    df = df[df["pCode"] <= 721000]
    # Filling 0s forward
    df["pCode"] = df["pCode"].apply(lambda x: str(x).zfill(6))
    # Close cursor
    cursor.close()
    # Close connection
    con.close()
    return df if len(portList) == 0 else df[df["pCode"].isin([elem.split("--")[1] for elem in portList])]

def dfCombine(date, portList = [], indClass = None):
    try:
        stcdf = get_indClass() if indClass == None else get_indClass(indClass)
        funddf = get_portMV(date, portList)
    except ValueError:
        return pd.DataFrame(data = None)
    df = pd.merge(stcdf, funddf, on = ["iName", "iCode"], how = "inner")
    return df

def top10Position(date, portList = []):
    """ 前十大持仓 """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    date = str(date)[0:10]
    df = dfCombine(date, portList)
    display(df)
    if df.shape[0] == 0:
        return display(HTML("""<p><b>没有记录</b></p>"""))
    df["iPCT"] = round(df["pMV"]/df["pTotNAV"], 3) * 100
    df = df.sort_values(["pCode", "iPCT"], ascending = False)
    df = df.groupby(['pCode'], group_keys = False).apply(lambda x: x.head(10)).reset_index(drop = True)
    df.set_index(["tDate", "pName", "pCode"], inplace = True)
    df = df[["iName", "iCode", "indClass1", "indClass2", "indClass3", "iPCT"]]
    df.index.names = ["交易日期", "组合名称", "组合代码"]
    df.columns = ["股票名称", "股票代码", "一级行业分类", "二级行业分类", "三级行业分类", "净值比(%)"]

    btn = wd.Button(description = "Save To CSV",
                    tooltip = 'Save data into local directory',
                    icon = "angle-double-down",
                    button_style = "info")

    def btn_click(sender):
        df.to_csv("../Results/%s_top10StockHLD.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_top10StockHLD.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

    btn.on_click(btn_click)
    clear()
    display(btn)
    out = wd.Output()
    display(out)
    display(df)
    # display(df.dtypes)
    return None


def top3IndPosition(date, indClass, portList = []):
    """ 前三大重仓行业和行业持有比例 """
    print('\x1b[100A\x1b[2K'+'\r***** '+'\x1b[1;31m'+'查询中...'+'\x1b[0m'+' *****', end='')
    date = str(date)[0:10]
    df = dfCombine(date, portList, indClass)
    if df.shape[0] == 0:
        return display(HTML("""<p><b>没有记录</b></p>"""))
    df = df.groupby(["pCode", "indClass"]).agg({"pName": "first", "tDate": "first", "pMV": "sum", "pTotNAV": "first"})
    df["indPCT"] = round(df["pMV"]/df["pTotNAV"] * 100, 1)
    df.reset_index(drop = False, inplace = True)
    # Within Group Ordering
    df = df.sort_values(["pCode", "indPCT"], ascending = False).groupby("pCode", group_keys = False).apply(lambda sub: sub.head(3))
    df = df[["tDate", "pName", "pCode", "indClass", "indPCT"]]
    res = pd.DataFrame(columns = ["交易日期", "组合名称", "组合代码", "第一大持仓行业", "第一大持仓占比(%)",
                       "第二大持仓行业", "第二大持仓占比(%)", "第三大持仓行业", "第三大持仓占比(%)"])
    for code in df["pCode"].unique():
        dfs = df[df["pCode"] == code]
        try:
            dic = {
                "交易日期": [dfs.iat[0,0]],
                "组合名称": [dfs.iat[0,1]],
                "组合代码": [dfs.iat[0,2]],
                "第一大持仓行业": [dfs.iat[0,3]],
                "第一大持仓占比(%)": [dfs.iat[0,4]],
                "第二大持仓行业": [dfs.iat[1,3]],
                "第二大持仓占比(%)": [dfs.iat[1,4]],
                "第三大持仓行业": [dfs.iat[2,3]],
                "第三大持仓占比(%)": [dfs.iat[2,4]]
            }
        except IndexError:
            try:
                dic = {
                    "交易日期": [dfs.iat[0,0]],
                    "组合名称": [dfs.iat[0,1]],
                    "组合代码": [dfs.iat[0,2]],
                    "第一大持仓行业": [dfs.iat[0,3]],
                    "第一大持仓占比(%)": [dfs.iat[0,4]],
                    "第二大持仓行业": [dfs.iat[1,3]],
                    "第二大持仓占比(%)": [dfs.iat[1,4]],
                    "第三大持仓行业": [None],
                    "第三大持仓占比(%)": [None]
                }
            except:
                try:
                    dic = {
                        "交易日期": [dfs.iat[0,0]],
                        "组合名称": [dfs.iat[0,1]],
                        "组合代码": [dfs.iat[0,2]],
                        "第一大持仓行业": [dfs.iat[0,3]],
                        "第一大持仓占比(%)": [dfs.iat[0,4]],
                        "第二大持仓行业": [None],
                        "第二大持仓占比(%)": [None],
                        "第三大持仓行业": [None],
                        "第三大持仓占比(%)": [None]
                    }
                except:
                    dic = {
                        "交易日期": [dfs.iat[0,0]],
                        "组合名称": [dfs.iat[0,1]],
                        "组合代码": [dfs.iat[0,2]],
                        "第一大持仓行业": [None],
                        "第一大持仓占比(%)": [None],
                        "第二大持仓行业": [None],
                        "第二大持仓占比(%)": [None],
                        "第三大持仓行业": [None],
                        "第三大持仓占比(%)": [None]
                    }
        res = res.append(pd.DataFrame(dic))
    res.set_index(["交易日期", "组合名称", "组合代码"], inplace = True)

    btn = wd.Button(description = "Save To CSV",
                        tooltip = 'Save data into local directory',
                        icon = "angle-double-down",
                        button_style = "info")

    def btn_click(sender):
        res.to_csv("../Results/%s_top3_Industry_Position.csv" % date.replace("-", ""), encoding="utf_8_sig")
        clear()
        with out:
            display(HTML("<p><b>保存成功! %s_top3_Industry_Position.csv文件已经被存入在Resutls文件夹下</b></p>" % date.replace("-", "")))

    btn.on_click(btn_click)
    clear()
    display(btn)
    out = wd.Output()
    display(out)
    display(res)
    return None

def top10StockPosition_interact():
    """ Industiral Concentration of Each Fund """
    pInfo = get_pInfo()
    pInfo = pInfo.sort_values("pCode", ascending = True)
    pInfo['comb'] = pInfo.apply(lambda x: '--'.join(x), axis=1)
    portList = wd.SelectMultiple(options = pInfo["comb"], value = [],
                     description = "选择特定组合", style = style, layout = Mul_Sel_Layout)

    x = wd.Text(value = '', placeholder = '每个组合代码间以分号分隔',
        description = '请输入组合代码(可多个)：', style = style, layout = Width_Layout)

    def f(x):
        if len(x) == 6:
            clear()
            values = [x]
            portList.value = tuple(pInfo['comb'][pInfo['pCode'].isin(values)])
        elif len(x) > 6:
            clear()
            values = x.replace(" ", "").split(";")
            portList.value = tuple(pInfo['comb'][pInfo['pCode'].isin(values)])
        elif (x != '') and (len(x) < 6):
            display(HTML("<b>请输入至少一个六位的组合代码，或者多个六位的组合代码（用分号分隔）</b>"))
        elif x == '':
            clear()
            portList.value = []

    int1 = wd.interact(f, x = x)
    display(int1)

    date = wd.DatePicker(value = yesterday, description = "选择日期")
    top10posi = wd.interact_manual(top10Position, date = date, portList = portList)
    top10posi.widget.children[2].description = "开始查询"
    top10posi.widget.children[2].button_style = "danger"
    display(top10posi)
    return None

def top3IndPosition_interact():
    pInfo = get_pInfo()
    pInfo = pInfo.sort_values("pCode", ascending = True)
    pInfo['comb'] = pInfo.apply(lambda x: '--'.join(x), axis=1)
    date = wd.DatePicker(value = yesterday, description = "选择日期")
    indClass = wd.Dropdown(value = "一级行业分类",
                            options = ["一级行业分类", "二级行业分类", "三级行业分类"],
                            description = '行业分类',
                           layout = Width_Layout)

    portList = wd.SelectMultiple(options = pInfo["comb"], value = [], description = "选择特定组合",
                                 style = style, layout = Mul_Sel_Layout)

    x = wd.Text(value = '', placeholder = '每个组合代码间以分号分隔',
        description = '请输入组合代码(可多个)：', style = style, layout = Width_Layout)

    def f(x):
        if len(x) == 6:
            clear()
            values = [x]
            portList.value = tuple(pInfo['comb'][pInfo['pCode'].isin(values)])
        elif len(x) > 6:
            clear()
            values = x.replace(" ", "").split(";")
            portList.value = tuple(pInfo['comb'][pInfo['pCode'].isin(values)])
        elif (x != '') and (len(x) < 6):
            display(HTML("<b>请输入至少一个六位的组合代码，或者多个六位的组合代码（用分号分隔）</b>"))
        elif x == '':
            clear()
            portList.value = []


    int1 = wd.interact(f, x = x)
    display(int1)


    top3hld = wd.interact_manual(top3IndPosition, date = date, indClass = indClass, portList = portList)
    top3hld.widget.children[3].description = "开始查询"
    top3hld.widget.children[3].button_style = "danger"
    display(top3hld)
    return None
