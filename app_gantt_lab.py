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
    limites = (6, 16, 36) if orientacao == "retrato" else (10, 24, 48)
    if meses <= limites[0]:
        return 1
    if meses <= limites[1]:
        return 3
    if meses <= limites[2]:
        return 6
    return 12


def margens_figura(orientacao, op, n_projetos):
    largura, altura = A4_PIXELS[orientacao]
    # A legenda ocupa espaco reservado (inclusive quando quebra em varias linhas).
    por_linha_aproximado = 3 if orientacao == "retrato" else 5
    linhas_legenda = max(1, math.ceil(n_projetos / por_linha_aproximado))
    inferior = min(int(altura * 0.27), 64 + linhas_legenda * (op.legenda + 10))
    return {
        "l": int(largura * op.largura_tarefas / 100),
        "r": 25,
        "t": 100,
        "b": inferior,
    }


def capacidade_pagina(orientacao, op, n_projetos):
    _, altura = A4_PIXELS[orientacao]
    margens = margens_figura(orientacao, op, n_projetos)
    altura_grafico = altura - margens["t"] - margens["b"]
    # Reservamos espaco para ate duas linhas de rotulo por atividade.
    altura_atividade = max(27, op.tarefas * op.espacamento)
    return max(1, int(altura_grafico // altura_atividade))


def dividir_dataframe(df, orientacao, op):
    n_projetos = df["Projeto"].nunique()
    capacidade = capacidade_pagina(orientacao, op, n_projetos)
    if op.dividir_paginas:
        paginas = [df.iloc[i : i + capacidade].copy() for i in range(0, len(df), capacidade)]
    else:
        paginas = [df.copy()]
    for pagina in paginas:
        pagina["y_idx"] = range(len(pagina))
    return paginas, capacidade


def quebra_tarefas(nome, max_caracteres, max_linhas=2):
    linhas = textwrap.wrap(str(nome), max(6, max_caracteres), break_long_words=False)
    if not linhas:
        return ""
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1].rstrip(" .") + "…"
    return "<br>".join(linhas)


def fig_gantt(pagina, df_completo, titulo, orientacao, op, numero_pagina, total_paginas):
    """Cria a unica figura-base usada tanto na tela como nas exportacoes PDF/PNG."""
    largura, altura = A4_PIXELS[orientacao]
    projetos_globais = df_completo["Projeto"].drop_duplicates().astype(str).tolist()
    cores = {projeto: CORES[i % len(CORES)] for i, projeto in enumerate(projetos_globais)}
    n_projetos = df_completo["Projeto"].nunique()
    margens = margens_figura(orientacao, op, n_projetos)

    dados = pagina.copy()
    # Fim inclusivo: barras tambem aparecem para atividades com um unico dia.
    dados["Fim_plot"] = dados["Fim"] + pd.Timedelta(days=1)
    fig = px.timeline(
        dados,
        x_start="Início",
        x_end="Fim_plot",
        y="y_idx",
        color="Projeto",
        color_discrete_map=cores,
        category_orders={"Projeto": projetos_globais},
        hover_data={
            "Projeto": True,
            "Tarefa": True,
            "Entrega_mensurável": True,
            "Início": "|%d/%m/%Y",
            "Fim": "|%d/%m/%Y",
            "Fim_plot": False,
            "y_idx": False,
        },
    )

    inicio_eixo, fim_eixo = intervalo_eixo(df_completo)
    intervalo = passo_tiques(numero_meses(df_completo), orientacao)
    meses_disponiveis = pd.date_range(inicio_eixo, fim_eixo, freq="MS")
    tiques = list(meses_disponiveis[::intervalo])
    rotulos_tiques = [
        (str(d.year) if intervalo >= 12 else f"{MESES[d.month - 1]}<br>{d.year}")
        for d in tiques
    ]

    # Rotulos truncados somente na figura. O hover conserva o texto original completo.
    caracteres = max(12, int((margens["l"] - 35) / (op.tarefas * 0.53)))
    ticktext = [quebra_tarefas(nome, caracteres) for nome in dados["Tarefa"]]
    fig.update_traces(width=0.62, marker_line_width=0)
    fig.update_yaxes(
        tickmode="array",
        tickvals=dados["y_idx"].tolist(),
        ticktext=ticktext,
        range=[len(dados) - 0.5, -0.5],
        tickfont=dict(size=op.tarefas, color="#263238"),
        showgrid=False,
        zeroline=False,
        title=None,
        automargin=False,
        ticks="",
    )
    fig.update_xaxes(
        range=[inicio_eixo, fim_eixo],
        tickmode="array",
        tickvals=tiques,
        ticktext=rotulos_tiques,
        tickfont=dict(size=op.datas, color="#344054"),
        gridcolor="#E4E9F0",
        gridwidth=1,
        showline=True,
        linecolor="#A5AFBC",
        zeroline=False,
        title=None,
        ticks="",
    )

    data_ini, data_fim = df_completo["Início"].min(), df_completo["Fim"].max()
    periodo = f"{data_ini:%d/%m/%Y} – {data_fim:%d/%m/%Y}"
    fig.update_layout(
        width=largura,
        height=altura,
        autosize=False,
        title=dict(
            text=f"{titulo}<br><sup>{periodo}</sup>",
            font=dict(size=op.titulo, color="#1C2735"),
            x=0.5,
            xanchor="center",
            y=0.973,
            yanchor="top",
        ),
        font=dict(family="Arial, sans-serif", size=op.datas, color="#202020"),
        margin=margens,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(
            title=None,
            orientation="h",
            x=0,
            xanchor="left",
            y=-0.10,
            yanchor="top",
            font=dict(size=op.legenda, color="#202020"),
            itemsizing="constant",
            tracegroupgap=3,
        ),
        bargap=0.38,
        hoverlabel=dict(font_size=13),
    )

    for indice in range(len(dados) - 1):
        if str(dados["Projeto"].iloc[indice]) != str(dados["Projeto"].iloc[indice + 1]):
            fig.add_shape(
                type="line", xref="x domain", yref="y",
                x0=0, x1=1, y0=indice + 0.5, y1=indice + 0.5,
                line=dict(color="#75808A", width=1, dash="dot"),
            )
    if total_paginas > 1:
        fig.add_annotation(
            x=0.99, y=0.0, xref="paper", yref="paper",
            xanchor="right", yanchor="top", yshift=-55,
            text=f"Página {numero_pagina}/{total_paginas}",
            showarrow=False, font=dict(size=11, color="#667085"),
        )
    return fig


def gerar_arquivos(figuras, orientacao, criar_png=True):
    """Exporta os proprios graficos Plotly. PDF e ajustado para A4, sem redesenho.

    O Plotly/Kaleido cria paginas PDF vetoriais. O PyMuPDF apenas ajusta a
    dimensao fisica e concatena as paginas, preservando exatamente o desenho.
    """
    import fitz  # pymupdf

    largura_pt, altura_pt = A4_PONTOS[orientacao]
    saida = fitz.open()
    imagens = []
    try:
        for i, fig in enumerate(figuras, start=1):
            # PDF vetorial vindo da MESMA figura exibida pelo Streamlit.
            pdf_plotly = fig.to_image(format="pdf", scale=1)
            origem = fitz.open(stream=pdf_plotly, filetype="pdf")
            try:
                destino = saida.new_page(width=largura_pt, height=altura_pt)
                destino.show_pdf_page(destino.rect, origem, 0, keep_proportion=False)
            finally:
                origem.close()

            if criar_png:
                imagens.append((i, fig.to_image(format="png", scale=2)))
        saida.set_metadata({"title": "Cronograma de Gantt", "creator": "Plotly/Kaleido"})
        pdf_bytes = saida.tobytes(garbage=4, deflate=True)
    finally:
        saida.close()

    if not imagens:
        return pdf_bytes, None, None
    if len(imagens) == 1:
        return pdf_bytes, imagens[0][1], "image/png"

    memoria_zip = BytesIO()
    with zipfile.ZipFile(memoria_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for numero, imagem in imagens:
            zf.writestr(f"gantt_pagina_{numero:02d}.png", imagem)
    return pdf_bytes, memoria_zip.getvalue(), "application/zip"


def mostrar_resultado(df, titulo, modo_impressao, op):
    orientacao = escolher_orientacao(modo_impressao, df)
    paginas, capacidade = dividir_dataframe(df, orientacao, op)
    total_paginas = len(paginas)
    largura_mm, altura_mm = (210, 297) if orientacao == "retrato" else (297, 210)

    st.subheader("Pré-visualização do Gantt")
    st.caption(
        f"A4 {orientacao} ({largura_mm} × {altura_mm} mm) · "
        f"{len(df)} atividades · {numero_meses(df)} meses · "
        f"{total_paginas} página(s)"
    )
    if len(df) > capacidade and not op.dividir_paginas:
        st.warning(
            "Este cronograma ultrapassa a capacidade da página com as fontes escolhidas. "
            "Ative 'Dividir em várias páginas' para evitar textos sobrepostos."
        )

    if total_paginas > 1:
        indice = st.select_slider(
            "Página da pré-visualização", options=list(range(1, total_paginas + 1)), value=1
        )
    else:
        indice = 1

    selecionada = fig_gantt(
        paginas[indice - 1], df, titulo, orientacao, op, indice, total_paginas
    )
    largura_px, altura_px = A4_PIXELS[orientacao]
    st.plotly_chart(
        selecionada,
        use_container_width=False,
        theme=None,
        config={
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"gantt_A4_{orientacao}_pagina_{indice}",
                "width": largura_px,
                "height": altura_px,
                "scale": 2,
            },
        },
    )
    st.caption(
        "Mova os controles de fonte na barra lateral: o gráfico acima é atualizado imediatamente. "
        "O PDF e o PNG serão exportados desta mesma figura Plotly."
    )

    # Hash inclui os dados e TODAS as configuracoes visuais, impedindo baixar
    # inadvertidamente um arquivo produzido com configuracoes anteriores.
    assinatura = sha256(
        (df.to_json(date_format="iso", orient="records") + titulo + orientacao
         + json.dumps(asdict(op), sort_keys=True)).encode("utf-8")
    ).hexdigest()

    st.divider()
    if st.button("Gerar PDF A4 e PNG com estas configurações", type="primary"):
        with st.spinner("Renderizando os gráficos Plotly para PDF e PNG..."):
            try:
                figuras = [
                    selecionada if i == indice else fig_gantt(
                        pagina, df, titulo, orientacao, op, i, total_paginas
                    )
                    for i, pagina in enumerate(paginas, start=1)
                ]
                pdf_bytes, png_bytes, png_tipo = gerar_arquivos(figuras, orientacao)
                st.session_state["exportacao_gantt"] = {
                    "assinatura": assinatura,
                    "pdf": pdf_bytes,
                    "png": png_bytes,
                    "png_tipo": png_tipo,
                    "orientacao": orientacao,
                }
            except Exception as exc:
                st.session_state.pop("exportacao_gantt", None)
                st.error(
                    "Não foi possível exportar o gráfico. A exportação requer "
                    "Kaleido e Chrome/Chromium no ambiente do Streamlit. "
                    "Confira requirements.txt e packages.txt, e reinicie o aplicativo."
                )
                with st.expander("Detalhes técnicos do erro"):
                    st.code(str(exc))

    pacote = st.session_state.get("exportacao_gantt", {})
    if pacote.get("assinatura") == assinatura:
        coluna_pdf, coluna_png = st.columns(2)
        with coluna_pdf:
            st.download_button(
                "Baixar PDF A4 (mesma aparência do Plotly)",
                data=pacote["pdf"],
                file_name=f"cronograma_A4_{orientacao}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with coluna_png:
            varios = total_paginas > 1
            st.download_button(
                "Baixar PNGs (.zip)" if varios else "Baixar PNG em alta resolução",
                data=pacote["png"],
                file_name=f"cronograma_A4_{orientacao}.zip" if varios
                else f"cronograma_A4_{orientacao}.png",
                mime=pacote["png_tipo"],
                use_container_width=True,
            )
    elif pacote:
        st.info("As configurações mudaram. Gere os arquivos novamente para obter a versão atualizada.")

    with st.expander("Ver atividades utilizadas"):
        st.dataframe(df.drop(columns=["y_idx"]), use_container_width=True)


# ----------------------------- INTERFACE ---------------------------------
st.title("Gráficos de Gantt para Projetos de Pesquisa")
st.markdown(
    f"Carregue uma planilha Excel ou preencha um cronograma manualmente. "
    f"Cada linha representa uma atividade com **Projeto**, **Tarefa**, **Início** e **Fim** "
    f"(DD-MM-AAAA). A coluna **Entrega_mensurável** é opcional. "
    f"[Baixar planilha modelo]({URL_PLANILHA_MODELO})."
)

st.sidebar.header("Entrada")
modo = st.sidebar.radio(
    "Modo de entrada",
    ["Carregar planilha Excel", "Preencher cronograma manualmente (sem Excel)"],
)
st.sidebar.divider()
st.sidebar.header("Formato da impressão")
modo_impressao = st.sidebar.selectbox(
    "Orientação", ["Automático", "A4 retrato", "A4 paisagem"],
    help="Automático escolhe paisagem para períodos extensos e poucos itens; retrato caso contrário.",
)
dividir_paginas = st.sidebar.checkbox(
    "Dividir em várias páginas se necessário", value=True,
    help="Preserva o tamanho das fontes em cronogramas longos.",
)
st.sidebar.divider()
st.sidebar.header("Tamanho das fontes")
fonte_titulo = st.sidebar.slider("Título", 12, 34, 22, 1)
fonte_tarefas = st.sidebar.slider("Nomes das tarefas", 8, 24, 15, 1)
fonte_datas = st.sidebar.slider("Datas do eixo horizontal", 8, 22, 13, 1)
fonte_legenda = st.sidebar.slider("Legenda dos projetos", 8, 22, 13, 1)
st.sidebar.header("Organização do gráfico")
largura_tarefas = st.sidebar.slider(
    "Espaço reservado para os nomes (%)", 25, 55, 39, 1,
    help="Aumente quando os nomes das atividades forem longos.",
)
espacamento = st.sidebar.slider(
    "Espaçamento entre tarefas", 1.8, 3.5, 2.55, 0.05,
    help="Um espaçamento maior permite fontes grandes, mas pode aumentar o número de páginas.",
)
opcoes = Opcoes(
    titulo=fonte_titulo,
    tarefas=fonte_tarefas,
    datas=fonte_datas,
    legenda=fonte_legenda,
    largura_tarefas=largura_tarefas,
    espacamento=espacamento,
    dividir_paginas=dividir_paginas,
)

if modo == "Carregar planilha Excel":
    st.subheader("Carregar planilha Excel")
    arquivo = st.file_uploader("Escolha o arquivo .xlsx", type=["xlsx"])
    if arquivo is not None:
        try:
            excel = pd.ExcelFile(arquivo)
            abas = excel.sheet_names
            if len(abas) == 1:
                aba = abas[0]
                st.caption(f"Aba utilizada: {aba}")
            else:
                aba = st.selectbox("Aba / pesquisador", options=abas)
            df, descartadas = validar_e_preparar(pd.read_excel(excel, sheet_name=aba))
        except Exception as exc:
            st.error(f"Erro ao ler a planilha: {exc}")
            st.stop()
        if descartadas:
            st.warning(f"{descartadas} linhas descartadas por datas inválidas ou fim anterior ao início.")
        if df.empty:
            st.warning("Nenhuma atividade válida encontrada nesta aba.")
        else:
            mostrar_resultado(df, f"Cronograma – {aba}", modo_impressao, opcoes)
    else:
        st.info("Envie um arquivo Excel para visualizar seu cronograma.")
else:
    st.subheader("Preenchimento manual")
    inicial = pd.DataFrame({
        "Projeto": ["Exemplo Projeto X", "Exemplo Projeto X"],
        "Tarefa": ["Planejamento do experimento", "Coleta de dados"],
        "Início": ["01-02-2026", "15-03-2026"],
        "Fim": ["28-02-2026", "30-04-2026"],
        "Entrega_mensurável": ["Protocolo experimental", "Banco de dados organizado"],
    })
    editado = st.data_editor(inicial, num_rows="dynamic", use_container_width=True, key="editor_gantt")
    if st.button("Gerar gráfico de Gantt"):
        st.session_state["mostrar_gantt_manual"] = True
    if st.session_state.get("mostrar_gantt_manual", False):
        try:
            df, descartadas = validar_e_preparar(editado)
        except Exception as exc:
            st.error(str(exc))
            st.stop()
        if descartadas:
            st.warning(f"{descartadas} linhas descartadas por datas inválidas ou fim anterior ao início.")
        if df.empty:
            st.warning("Preencha pelo menos uma atividade válida.")
        else:
            mostrar_resultado(df, "Cronograma – entrada manual", modo_impressao, opcoes)
