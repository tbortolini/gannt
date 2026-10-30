"""Aplicacao Streamlit de cronogramas de pesquisa, com PDF vetorial A4.

Execucao: streamlit run gantt_streamlit_a4.py
Dependencias: streamlit, pandas, openpyxl, plotly, reportlab.
"""

from io import BytesIO
import textwrap

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit


st.set_page_config(page_title="Gantt - Cronogramas de Pesquisa", layout="wide")

URL_PLANILHA_MODELO = (
    "https://github.com/tbortolini/gannt/raw/main/exemplo_cronograma.xlsx"
)

COLUNAS_OBRIGATORIAS = ["Projeto", "Tarefa", "Início", "Fim"]
CORES = px.colors.qualitative.Plotly
MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# As fontes sao usadas somente dentro do PDF. Se indisponiveis,
# o ReportLab usa as fontes padrao (Helvetica).
FONTE = "Helvetica"
FONTE_NEGRITO = "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("GanttDejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("GanttDejaVuBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    FONTE, FONTE_NEGRITO = "GanttDejaVu", "GanttDejaVuBold"
except Exception:
    pass


def validar_e_preparar(df):
    """Normaliza o Excel/editor, retira linhas incompletas e ordena atividades."""
    faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
    if faltantes:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(faltantes))

    resultado = df.copy()
    if "Entrega_mensurável" not in resultado.columns:
        resultado["Entrega_mensurável"] = ""

    for col in ["Projeto", "Tarefa"]:
        resultado[col] = resultado[col].astype("string").str.strip().replace("", pd.NA)
    resultado["Entrega_mensurável"] = resultado["Entrega_mensurável"].fillna("").astype(str)
    resultado = resultado.dropna(subset=["Projeto", "Tarefa", "Início", "Fim"])

    for col in ["Início", "Fim"]:
        resultado[col] = pd.to_datetime(resultado[col], dayfirst=True, errors="coerce")
    antes = len(resultado)
    resultado = resultado.dropna(subset=["Início", "Fim"])
    resultado = resultado[resultado["Fim"] >= resultado["Início"]].copy()
    descartadas = antes - len(resultado)

    resultado = resultado.sort_values(["Projeto", "Início", "Tarefa"]).reset_index(drop=True)
    resultado["y_idx"] = range(len(resultado))
    return resultado, descartadas


def intervalo_eixo(df):
    inicio = df["Início"].min().replace(day=1)
    fim = (df["Fim"].max() + pd.offsets.MonthBegin(1)).normalize()
    return inicio, fim


def numero_meses(df):
    inicio, fim = intervalo_eixo(df)
    return max(1, (fim.year - inicio.year) * 12 + fim.month - inicio.month)


def escolher_orientacao(modo, df):
    if modo == "A4 retrato":
        return "retrato"
    if modo == "A4 paisagem":
        return "paisagem"
    # Em geral, retrato comporta mais atividades; paisagem favorece duracoes longas.
    n = len(df)
    meses = numero_meses(df)
    if (meses > 12 and n <= 20) or (meses > 24 and n <= 24):
        return "paisagem"
    return "retrato"


def dimensoes(orientacao):
    # Pontos tipograficos (1 pt = 1/72 polegada): A4 verdadeiro.
    return A4 if orientacao == "retrato" else landscape(A4)


def abreviar_texto(texto, limite, max_linhas=2):
    """Utilizado somente no eixo Y da visualizacao; hover mostra texto integral."""
    linhas = textwrap.wrap(str(texto), width=limite, break_long_words=True)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1].rstrip(" .") + "…"
    return "<br>".join(linhas) if linhas else ""


def intervalo_tique(meses, orientacao):
    # Reduz a densidade de datas, sobretudo no A4 retrato.
    limites = (6, 16, 36) if orientacao == "retrato" else (11, 28, 54)
    if meses <= limites[0]:
        return 1
    if meses <= limites[1]:
        return 3
    if meses <= limites[2]:
        return 6
    return 12


def fig_gantt(df, titulo, orientacao):
    """Previsualizacao Plotly com a mesma proporcao da folha A4."""
    largura, altura = dimensoes(orientacao)
    largura, altura = round(largura), round(altura)
    projetos = df["Projeto"].drop_duplicates().tolist()
    cores = {p: CORES[i % len(CORES)] for i, p in enumerate(projetos)}
    df_plot = df.copy()
    # Datas de fim sao inclusivas no cronograma (inclusive tarefas de um dia).
    df_plot["Fim_plot"] = df_plot["Fim"] + pd.Timedelta(days=1)

    fig = px.timeline(
        df_plot,
        x_start="Início",
        x_end="Fim_plot",
        y="y_idx",
        color="Projeto",
        color_discrete_map=cores,
        category_orders={"Projeto": projetos},
        hover_data={
            "Projeto": True, "Tarefa": True, "Entrega_mensurável": True,
            "Início": "|%d/%m/%Y", "Fim": "|%d/%m/%Y",
            "Fim_plot": False, "y_idx": False,
        },
    )

    inicio_eixo, fim_eixo = intervalo_eixo(df)
    fonte = 8 if orientacao == "retrato" else 9
    largura_tarefa = 22 if orientacao == "retrato" else 31
    nomes = [abreviar_texto(x, largura_tarefa) for x in df["Tarefa"]]
    # O numero de projetos pode fazer a legenda ocupar varias linhas;
    # simplificamos a legenda e reservamos espaco na parte inferior.
    altura_linha_preview = (altura - (135 if len(projetos) > 4 else 115)) / max(1, len(df))
    fig.update_traces(width=min(0.60, 16 / max(1, altura_linha_preview)))
    fig.update_yaxes(
        tickmode="array",
        tickvals=df["y_idx"].tolist(),
        ticktext=nomes,
        range=[len(df) - 0.5, -0.5],
        tickfont=dict(size=fonte, color="#202020"),
        showgrid=False,
        zeroline=False,
        title=None,
        automargin=False,
    )
    fig.update_xaxes(
        range=[inicio_eixo, fim_eixo],
        dtick=f"M{intervalo_tique(numero_meses(df), orientacao)}",
        tickformat="%b<br>%Y",
        tickfont=dict(size=8, color="#202020"),
        gridcolor="#E5E9EF",
        linecolor="#808080",
        showline=True,
        title=None,
    )
    fig.update_layout(
        width=largura,
        height=altura,
        autosize=False,
        title=dict(text=titulo, font=dict(size=12 if orientacao == "retrato" else 14), x=0.04),
        font=dict(family="Arial", size=9, color="#202020"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(
            l=172 if orientacao == "retrato" else 214,
            r=18,
            t=55,
            b=83 if len(projetos) > 4 else 65,
        ),
        legend=dict(
            title=None,
            orientation="h",
            x=0,
            xanchor="left",
            y=-0.065,
            yanchor="top",
            font=dict(size=8),
            itemsizing="constant",
        ),
        bargap=0.35,
    )

    # Separadores entre projetos: o eixo Y e numerico (indices 0, 1, ...).
    for i in range(len(df) - 1):
        if df["Projeto"].iloc[i] != df["Projeto"].iloc[i + 1]:
            fig.add_shape(
                type="line", xref="x domain", yref="y",
                x0=0, x1=1, y0=i + 0.5, y1=i + 0.5,
                line=dict(color="#505050", width=1, dash="dot"),
            )
    return fig


def limitar_largura_pdf(texto, largura_max, fonte, tamanho):
    texto = str(texto)
    if pdfmetrics.stringWidth(texto, fonte, tamanho) <= largura_max:
        return texto
    while texto and pdfmetrics.stringWidth(texto + "…", fonte, tamanho) > largura_max:
        texto = texto[:-1]
    return texto + "…"


def legenda_pdf(c, projetos, cores, largura, y_inicial):
    """Desenha legenda responsiva e retorna a coordenada abaixo da legenda."""
    x = 26
    y = y_inicial
    for projeto in projetos:
        nome = limitar_largura_pdf(projeto, 150, FONTE, 7)
        tamanho = 10 + 5 + pdfmetrics.stringWidth(nome, FONTE, 7) + 15
        if x + tamanho > largura - 25 and x > 26:
            x = 26
            y -= 13
        c.setFillColor(colors.HexColor(cores[projeto]))
        c.roundRect(x, y - 1, 8, 8, 1.5, stroke=0, fill=1)
        c.setFont(FONTE, 7)
        c.setFillColor(colors.HexColor("#303030"))
        c.drawString(x + 13, y, nome)
        x += tamanho
    return y - 15


def gerar_pdf_a4(df, titulo, orientacao, dividir_paginas=True):
    """Exportacao PDF vetorial e dimensoes fisicas A4, sem Kaleido/Chrome."""
    largura, altura = dimensoes(orientacao)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(largura, altura), pageCompression=1)
    pdf.setTitle(titulo)

    projetos = df["Projeto"].drop_duplicates().tolist()
    cores = {p: CORES[i % len(CORES)] for i, p in enumerate(projetos)}
    inicio_eixo, fim_eixo = intervalo_eixo(df)
    duracao = max((fim_eixo - inicio_eixo).total_seconds(), 1)
    tick_step = intervalo_tique(numero_meses(df), orientacao)

    # Determina a capacidade sem reduzir as fontes abaixo do legivel.
    # A legenda usa o mesmo espaco em todas as paginas.
    legenda_y_fake = altura - 66
    x_sim = 26
    for projeto in projetos:
        nome = limitar_largura_pdf(projeto, 150, FONTE, 7)
        tam = 10 + 5 + pdfmetrics.stringWidth(nome, FONTE, 7) + 15
        if x_sim + tam > largura - 25 and x_sim > 26:
            x_sim = 26
            legenda_y_fake -= 13
        x_sim += tam
    topo_grafico = legenda_y_fake - 39
    base_grafico = 43
    altura_util = topo_grafico - base_grafico
    capacidade = max(1, int(altura_util // 21))

    if dividir_paginas:
        blocos = [df.iloc[i:i + capacidade] for i in range(0, len(df), capacidade)]
    else:
        blocos = [df]

    esquerda = 26
    largura_texto = 168 if orientacao == "retrato" else 219
    x_tempo = esquerda + largura_texto
    largura_tempo = largura - 25 - x_tempo

    def x_data(data):
        fracao = (pd.Timestamp(data) - inicio_eixo).total_seconds() / duracao
        return x_tempo + min(1, max(0, fracao)) * largura_tempo

    for numero_pagina, bloco in enumerate(blocos, 1):
        pdf.setFillColor(colors.HexColor("#192536"))
        pdf.setFont(FONTE_NEGRITO, 12 if orientacao == "retrato" else 13)
        pdf.drawString(esquerda, altura - 30, limitar_largura_pdf(titulo, largura - 50, FONTE_NEGRITO, 12))
        pdf.setFont(FONTE, 7.5)
        pdf.setFillColor(colors.HexColor("#667085"))
        periodo = f"{df['Início'].min():%d/%m/%Y} a {df['Fim'].max():%d/%m/%Y}  |  {len(df)} atividades"
        pdf.drawString(esquerda, altura - 46, periodo)
        legenda_pdf(pdf, projetos, cores, largura, altura - 66)

        pdf.setFont(FONTE_NEGRITO, 8)
        pdf.setFillColor(colors.HexColor("#374151"))
        pdf.drawString(esquerda, topo_grafico + 10, "Tarefas")
        pdf.drawString(x_tempo + 3, topo_grafico + 10, "Cronograma")

        n = len(bloco)
        altura_linha = altura_util / max(1, n)
        tamanho_fonte = min(9.5, max(5.5, altura_linha * 0.35))
        barra_altura = min(14, max(2.5, altura_linha * 0.52))

        # Faixas horizontais discretas para facilitar a leitura.
        for j in range(n):
            if j % 2 == 1:
                pdf.setFillColor(colors.HexColor("#F8FAFD"))
                pdf.rect(esquerda, topo_grafico - (j + 1) * altura_linha,
                         largura - esquerda - 25, altura_linha, stroke=0, fill=1)

        # Datas e linhas verticais do eixo temporal.
        meses = pd.date_range(inicio_eixo, fim_eixo, freq="MS")
        for indice, data in enumerate(meses):
            if indice % tick_step != 0:
                continue
            pos = x_data(data)
            pdf.setStrokeColor(colors.HexColor("#E0E5ED"))
            pdf.setLineWidth(0.45)
            pdf.line(pos, base_grafico, pos, topo_grafico)
            rotulo = f"{MESES_PT[data.month - 1]}/{str(data.year)[-2:]}" if tick_step < 12 else str(data.year)
            pdf.setFont(FONTE, 6.5)
            pdf.setFillColor(colors.HexColor("#526071"))
            largura_rotulo = pdfmetrics.stringWidth(rotulo, FONTE, 6.5)
            pdf.drawString(max(x_tempo, min(pos - largura_rotulo / 2,
                                            largura - 25 - largura_rotulo)),
                           topo_grafico + 1, rotulo)

        pdf.setStrokeColor(colors.HexColor("#D1D9E4"))
        pdf.line(x_tempo, base_grafico, x_tempo, topo_grafico)
        pdf.line(esquerda, base_grafico, largura - 25, base_grafico)

        for j, (_, atividade) in enumerate(bloco.iterrows()):
            y = topo_grafico - (j + 0.5) * altura_linha
            tarefa = str(atividade["Tarefa"])
            linhas = simpleSplit(tarefa, FONTE, tamanho_fonte, largura_texto - 10)
            if not linhas:
                linhas = [""]
            linhas = linhas[:2]
            if len(simpleSplit(tarefa, FONTE, tamanho_fonte, largura_texto - 10)) > 2:
                linhas[-1] = limitar_largura_pdf(linhas[-1] + "…", largura_texto - 10,
                                                  FONTE, tamanho_fonte)

            pdf.setFillColor(colors.HexColor("#1F2937"))
            pdf.setFont(FONTE, tamanho_fonte)
            if len(linhas) == 1:
                pdf.drawString(esquerda + 2, y - 2.5, linhas[0])
            else:
                pdf.drawString(esquerda + 2, y + 1.2, linhas[0])
                pdf.drawString(esquerda + 2, y - tamanho_fonte - 0.4, linhas[1])

            projeto = str(atividade["Projeto"])
            x1 = x_data(atividade["Início"])
            x2 = x_data(atividade["Fim"] + pd.Timedelta(days=1))
            pdf.setFillColor(colors.HexColor(cores[projeto]))
            pdf.roundRect(x1, y - barra_altura / 2, max(2.5, x2 - x1),
                          barra_altura, min(3, barra_altura / 3), stroke=0, fill=1)

            # Separacao pontilhada ao mudar de projeto, dentro da pagina.
            if j + 1 < n and atividade["Projeto"] != bloco.iloc[j + 1]["Projeto"]:
                pdf.setStrokeColor(colors.HexColor("#9CA3AF"))
                pdf.setDash(2, 2)
                pdf.line(esquerda, topo_grafico - (j + 1) * altura_linha,
                         largura - 25, topo_grafico - (j + 1) * altura_linha)
                pdf.setDash()

        pdf.setFillColor(colors.HexColor("#6B7280"))
        pdf.setFont(FONTE, 7)
        pdf.drawRightString(largura - 25, 25,
                            f"Página {numero_pagina}/{len(blocos)}  |  A4 {orientacao}")
        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue(), len(blocos), capacidade


def mostrar_resultado(df, titulo, modo_impressao, dividir_paginas):
    orientacao = escolher_orientacao(modo_impressao, df)
    largura, altura = dimensoes(orientacao)
    meses = numero_meses(df)

    st.subheader("Gráfico de Gantt")
    st.caption(
        f"Formato selecionado: **A4 {orientacao}** ("
        f"{largura / 72 * 25.4:.0f} × {altura / 72 * 25.4:.0f} mm) · "
        f"{len(df)} atividades · período de aproximadamente {meses} meses"
    )
    fig = fig_gantt(df, titulo, orientacao)
    # A previsualizacao nao expande indefinidamente ate a largura da tela.
    # O icone da camera exporta uma imagem com a proporcao A4, em alta resolucao.
    st.plotly_chart(
        fig,
        use_container_width=False,
        theme=None,
        config={
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"cronograma_A4_{orientacao}",
                "width": round(largura),
                "height": round(altura),
                "scale": 3,
            },
        },
    )

    pdf_bytes, total_paginas, capacidade = gerar_pdf_a4(
        df, titulo, orientacao, dividir_paginas=dividir_paginas
    )
    st.download_button(
        label=f"📄 Baixar PDF A4 {orientacao} ({total_paginas} página(s))",
        data=pdf_bytes,
        file_name=f"cronograma_gantt_A4_{orientacao}.pdf",
        mime="application/pdf",
        use_container_width=False,
    )
    st.caption("Para PNG, use o ícone de câmera no gráfico; para imprimir, prefira o PDF vetorial.")
    if len(df) > capacidade and not dividir_paginas:
        st.warning(
            "Há muitas atividades para uma única folha A4 neste formato. "
            "O PDF foi mantido em uma página, mas as letras podem ficar pequenas. "
            "Ative a opção de dividir em páginas para melhorar a leitura."
        )
    if total_paginas > 1:
        st.info(
            f"O PDF foi dividido em {total_paginas} páginas A4 para manter as tarefas legíveis; "
            "todas utilizam a mesma escala temporal."
        )
    with st.expander("Ver tabela de atividades utilizada"):
        st.dataframe(df.drop(columns=["y_idx"]), use_container_width=True)


# --------------------------- INTERFACE -------------------------------------
st.title("Geração de Gráficos de Gantt para Projetos de Pesquisa")
st.markdown(
    f"""Envie uma planilha Excel ou preencha o cronograma manualmente.

    Cada atividade precisa de **Projeto**, **Tarefa**, **Início** e **Fim**;
    a coluna **Entrega_mensurável** é recomendada, mas opcional.
    As datas devem seguir **DD-MM-AAAA**.

    [Baixar planilha modelo]({URL_PLANILHA_MODELO})
    """
)
st.sidebar.header("Entrada de dados")
modo = st.sidebar.radio(
    "Escolha como inserir o cronograma:",
    ["Carregar planilha Excel", "Preencher cronograma manualmente (sem Excel)"],
)
st.sidebar.divider()
st.sidebar.header("Impressão e exportação")
modo_impressao = st.sidebar.selectbox(
    "Orientação da página",
    ["Automático", "A4 retrato", "A4 paisagem"],
    help="Automático prefere retrato para muitas atividades e paisagem para prazos extensos.",
)
dividir_paginas = st.sidebar.checkbox(
    "Dividir em páginas se necessário",
    value=True,
    help="Mantém o texto legível quando as atividades não cabem confortavelmente em uma folha.",
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
            dados = pd.read_excel(excel, sheet_name=aba)
            df_g, descartadas = validar_e_preparar(dados)
        except Exception as e:
            st.error(f"Erro ao ler a planilha: {e}")
            st.stop()

        if descartadas:
            st.warning(f"{descartadas} atividade(s) removida(s): datas inválidas ou fim anterior ao início.")
        if df_g.empty:
            st.warning("Não há atividades válidas na aba selecionada.")
        else:
            mostrar_resultado(df_g, f"Cronograma - {aba}", modo_impressao, dividir_paginas)
    else:
        st.info("Envie sua planilha para gerar o gráfico.")

else:
    st.subheader("Preencher cronograma manualmente")
    inicial = pd.DataFrame({
        "Projeto": ["Exemplo Projeto X", "Exemplo Projeto X"],
        "Tarefa": ["Planejamento experimento", "Coleta de dados"],
        "Início": ["01-02-2025", "15-03-2025"],
        "Fim": ["28-02-2025", "30-04-2025"],
        "Entrega_mensurável": [
            "Documento de protocolo experimental", "Banco de dados bruto organizado"
        ],
    })
    editado = st.data_editor(inicial, num_rows="dynamic", use_container_width=True, key="editor_gantt")
    if st.button("Gerar gráfico de Gantt"):
        st.session_state["mostrar_gantt_manual"] = True
    if st.session_state.get("mostrar_gantt_manual", False):
        try:
            df_g, descartadas = validar_e_preparar(editado)
        except Exception as e:
            st.error(str(e))
            st.stop()
        if descartadas:
            st.warning(f"{descartadas} atividade(s) removida(s): datas inválidas ou fim anterior ao início.")
        if df_g.empty:
            st.warning("Preencha pelo menos uma atividade com todas as datas válidas.")
        else:
            mostrar_resultado(df_g, "Cronograma - entrada manual", modo_impressao, dividir_paginas)
