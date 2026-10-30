"""Gantt para pesquisa: fontes ajustaveis e PDF/PNG identicos ao Plotly.

Execucao: streamlit run gantt_streamlit_A4_fontes_Plotly.py

Requisitos Python: streamlit, pandas, openpyxl, plotly>=6.1, kaleido>=1, pymupdf
Requisito adicional para exportacao Kaleido v1: Chrome ou Chromium.
Em Streamlit Community Cloud, inclua os arquivos requirements.txt e packages.txt
na raiz do repositorio. O arquivo packages.txt instala Chromium no servidor.
"""

from dataclasses import dataclass, asdict
from hashlib import sha256
from io import BytesIO
import json
import math
import textwrap
import zipfile

import pandas as pd
import plotly.express as px
import streamlit as st

# O PyMuPDF e importado somente quando um PDF for gerado.
# Assim, a pre-visualizacao continua funcionando mesmo em caso de erro de exportacao.

st.set_page_config(page_title="Gantt - Cronogramas de Pesquisa", layout="wide")

URL_PLANILHA_MODELO = "https://github.com/tbortolini/gannt/raw/main/exemplo_cronograma.xlsx"
COLUNAS_OBRIGATORIAS = ["Projeto", "Tarefa", "Início", "Fim"]
CORES = px.colors.qualitative.Plotly
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Dimensoes de um A4 em pontos (PDF, 72 pt/polegada) e pixels logicos (Plotly, 96 dpi).
# O PDF vetorial original do Plotly sera redimensionado para uma pagina A4 exata.
A4_PONTOS = {"retrato": (595.2756, 841.8898), "paisagem": (841.8898, 595.2756)}
A4_PIXELS = {"retrato": (794, 1123), "paisagem": (1123, 794)}


@dataclass(frozen=True)
class Opcoes:
    titulo: int = 22
    tarefas: int = 15
    datas: int = 13
    legenda: int = 13
    largura_tarefas: int = 39   # porcentagem da largura total
    espacamento: float = 2.55  # altura minima por tarefa em multiplos do tamanho da fonte
    dividir_paginas: bool = True


def validar_e_preparar(df):
    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltantes:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(faltantes))

    resultado = df.copy()
    if "Entrega_mensurável" not in resultado.columns:
        resultado["Entrega_mensurável"] = ""
    for coluna in ["Projeto", "Tarefa"]:
        resultado[coluna] = resultado[coluna].astype("string").str.strip().replace("", pd.NA)
    resultado["Entrega_mensurável"] = resultado["Entrega_mensurável"].fillna("").astype(str)
    resultado = resultado.dropna(subset=COLUNAS_OBRIGATORIAS)

    for coluna in ["Início", "Fim"]:
        resultado[coluna] = pd.to_datetime(resultado[coluna], dayfirst=True, errors="coerce")
    anteriores = len(resultado)
    resultado = resultado.dropna(subset=["Início", "Fim"])
    resultado = resultado.loc[resultado["Fim"] >= resultado["Início"]].copy()
    descartadas = anteriores - len(resultado)
    resultado = resultado.sort_values(["Projeto", "Início", "Tarefa"]).reset_index(drop=True)
    resultado["y_idx"] = range(len(resultado))
    return resultado, descartadas


def intervalo_eixo(df):
    inicio = df["Início"].min().replace(day=1).normalize()
    fim = (df["Fim"].max() + pd.offsets.MonthBegin(1)).normalize()
    if fim <= inicio:
        fim = inicio + pd.DateOffset(months=1)
    return inicio, fim


def numero_meses(df):
    inicio, fim = intervalo_eixo(df)
    return max(1, (fim.year - inicio.year) * 12 + fim.month - inicio.month)


def escolher_orientacao(modo, df):
    if modo == "A4 retrato":
        return "retrato"
    if modo == "A4 paisagem":
        return "paisagem"
    meses, atividades = numero_meses(df), len(df)
    return "paisagem" if (meses > 12 and atividades <= 20) or (meses > 24 and atividades <= 24) else "retrato"


def passo_tiques(meses, orientacao):
