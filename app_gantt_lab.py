
# ======================================
# CONFIGURAÇÃO INICIAL DA APLICAÇÃO
# ======================================

st.set_page_config(
    page_title="Gantt – Cronogramas de Pesquisa",
    layout="wide"
)

# 👉 Ajuste esta URL para o link real da planilha modelo no repositório
URL_PLANILHA_MODELO = (
    "https://github.com/SEU_USUARIO/SEU_REPOSITORIO/raw/main/exemplo_cronograma.xlsx"
)

st.title("Geração de Gráficos de Gantt para Projetos de Pesquisa")

st.markdown(
    f"""
    ## Instruções gerais para preenchimento

    Esta aplicação permite que cada pesquisador **defina e visualize o seu cronograma**
    de forma padronizada, gerando um gráfico de Gantt automaticamente.

    🔗 Se preferir, você pode baixar um **modelo de planilha Excel** já formatado aqui:  
    👉 [Baixar planilha modelo]({URL_PLANILHA_MODELO})

    ### Estrutura das atividades

    - Cada linha do cronograma representa **uma atividade**.
    - Para cada atividade, preencha:
      - **Projeto** – nome do projeto ou subprojeto (ex.: `Dowsing`, `GML`, etc.).
      - **Tarefa** – o que será feito em termos operacionais (ex.: `Coleta de dados fase 1`).
      - **Início** – data de início no formato **DD-MM-YYYY** (ex.: `01-03-2025`).
      - **Fim** – data de fim no formato **DD-MM-YYYY** (ex.: `31-05-2025`).
      - **Entrega_mensurável** – qual é o resultado concreto ao final dessa atividade
        (ex.: para `Coleta de dados`, a entrega pode ser `Banco de dados organizado`).

    ### Sobre as entregas mensuráveis

    Cada atividade do cronograma **deve ter uma entrega mensurável**.  
    Isso ajuda a conectar o cronograma com resultados concretos e verificáveis.

    Alguns exemplos:

    - `Revisão da literatura` → entrega: **arquivo com revisão inicial** ou **bibliografia organizada em um gerenciador (Zotero, Mendeley)**.  
    - `Coleta de dados` → entrega: **banco de dados em formato padronizado**.  
    - `Análise de dados preliminar` → entrega: **notebook com análises exploratórias**.  
    - `Redação do artigo (introdução)` → entrega: **rascunho da seção de introdução**.

    Você pode usar tanto **upload de planilha Excel** quanto **preenchimento manual na própria tela**.
    """
)

st.divider()

# ======================================
# FUNÇÕES AUXILIARES
# ======================================

def carregar_df_de_excel(xls, aba):
    """
    Carrega e prepara o DataFrame a partir de uma aba de Excel.
    Espera colunas:
      - Projeto
      - Tarefa
      - Início
      - Fim
      - (opcional) Entrega_mensurável
    Datas no formato DD-MM-YYYY.
    """
    df = pd.read_excel(xls, sheet_name=aba)

    col_obrig = ["Projeto", "Tarefa", "Início", "Fim"]
    for c in col_obrig:
        if c not in df.columns:
            raise ValueError(f"A aba '{aba}' não contém a coluna obrigatória: {c}")

    # Se não existir coluna de entrega, cria vazia
    if "Entrega_mensurável" not in df.columns:
        df["Entrega_mensurável"] = ""

    df["Início"] = pd.to_datetime(df["Início"], dayfirst=True, errors="coerce")
    df["Fim"] = pd.to_datetime(df["Fim"], dayfirst=True, errors="coerce")

    # Remove linhas com datas inválidas
    df = df.dropna(subset=["Início", "Fim"])

    return df


def preparar_df_para_gantt(df):
    """
    Ordena por Projeto e Início e adiciona um índice numérico 'y_idx'
    para controlar a posição no eixo Y e permitir desenhar linhas entre projetos.
    """
    df_g = df.copy()
    df_g = df_g.sort_values(by=["Projeto", "Início"]).reset_index(drop=True)
    df_g["y_idx"] = df_g.index  # posição numérica para o eixo Y
    return df_g


def fig_gantt(df, titulo):
    """
    Cria figura Plotly de Gantt a partir de:
      - Projeto
      - Tarefa
      - Início
      - Fim
      - y_idx (posição no eixo Y)
    Com:
      - fundo branco
      - todos os textos em preto
      - linha preta pontilhada entre projetos
    """
    # Garantir que existe y_idx
    if "y_idx" not in df.columns:
        df = preparar_df_para_gantt(df)

    fig = px.timeline(
        df,
        x_start="Início",
        x_end="Fim",
        y="y_idx",
        color="Projeto",
        title=titulo,
        hover_data=["Projeto", "Tarefa", "Entrega_mensurável"]
        if "Entrega_mensurável" in df.columns
        else ["Projeto", "Tarefa"]
    )

    # Substituir ticks numéricos pelos nomes das tarefas
    fig.update_yaxes(
        tickmode="array",
        tickvals=df["y_idx"],
        ticktext=df["Tarefa"],
        autorange="reversed",
        tickfont=dict(color="black"),
        title_font=dict(color="black")
    )

    fig.update_xaxes(
        tickfont=dict(color="black"),
        title_font=dict(color="black"),
        linecolor="black",
        gridcolor="lightgray"
    )

    # Fundo branco + textos em preto
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="black"),
        xaxis_title="Tempo",
        yaxis_title="Tarefas",
        legend_title="Projeto",
        legend=dict(
            font=dict(color="black"),
            title_font=dict(color="black")
        ),
        margin=dict(l=50, r=30, t=70, b=50),
    )

    # Linhas pretas pontilhadas entre projetos
    shapes = []
    for i in range(len(df) - 1):
        projeto_atual = df["Projeto"].iloc[i]
        proximo_projeto = df["Projeto"].iloc[i + 1]
        if projeto_atual != proximo_projeto:
            shapes.append(
                dict(
                    type="line",
                    xref="x domain",
                    yref="y",
                    x0=0,
                    x1=1,
                    y0=i + 0.5,
                    y1=i + 0.5,
                    line=dict(color="black", width=1, dash="dot"),
                )
            )

    if shapes:
        fig.update_layout(shapes=shapes)

    return fig


# ======================================
# ESCOLHA DO MODO DE ENTRADA
# ======================================

st.sidebar.header("Modo de uso")

modo = st.sidebar.radio(
    "Escolha como quer inserir o cronograma:",
    [
        "Carregar planilha Excel",
        "Preencher cronograma manualmente (sem Excel)",
    ]
)

# ======================================
# MODO 1: UPLOAD DE PLANILHA EXCEL
# ======================================

if modo == "Carregar planilha Excel":
    st.subheader("Modo: Carregar planilha Excel")

    st.markdown(
        f"""
        **Formato esperado da planilha:**

        - Arquivo Excel (`.xlsx`).
        - Você pode usar:
          - **Uma aba por pesquisador**, com as colunas:
            - `Projeto`
            - `Tarefa`
            - `Início` (DD-MM-YYYY)
            - `Fim` (DD-MM-YYYY)
            - `Entrega_mensurável` (opcional, mas fortemente recomendada)
          - Ou uma única aba com esses mesmos campos.

        Cada linha da planilha deve representar **uma atividade**.

        Se tiver dúvidas, use o modelo:  
        👉 [Baixar planilha modelo]({URL_PLANILHA_MODELO})
        """
    )

    uploaded_file = st.file_uploader(
        "Faça upload da planilha Excel",
        type=["xlsx"]
    )

    if uploaded_file is not None:
        try:
            xls = pd.ExcelFile(uploaded_file)
            abas = xls.sheet_names
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.stop()

        if len(abas) == 1:
            aba_escolhida = abas[0]
            st.info(f"Arquivo possui uma única aba. Usando: **{aba_escolhida}**")
        else:
            aba_escolhida = st.selectbox(
                "Selecione a aba (pesquisador) a visualizar",
                options=abas
            )

        try:
            df = carregar_df_de_excel(xls, aba_escolhida)
        except Exception as e:
            st.error(f"Erro ao carregar a aba '{aba_escolhida}': {e}")
            st.stop()

        st.markdown("### Pré-visualização da tabela")
        st.dataframe(df)

        df_g = preparar_df_para_gantt(df)

        st.markdown("### Gráfico de Gantt")
        fig = fig_gantt(df_g, f"Cronograma – {aba_escolhida}")
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "💾 Para salvar o gráfico como imagem, clique no ícone de **câmera** "
            "no canto superior direito do gráfico (\"Download plot as png\")."
        )

    else:
        st.info("Envie um arquivo Excel para gerar o gráfico de Gantt.")


# ======================================
# MODO 2: PREENCHIMENTO MANUAL COM DATA_EDITOR
# ======================================

else:
    st.subheader("Modo: Preencher cronograma manualmente (sem Excel)")

    st.markdown(
        """
        Use a tabela abaixo para montar o seu cronograma diretamente na aplicação.

        - Você pode **editar as células**, **adicionar linhas** e **remover linhas**.
        - Datas devem ser informadas no formato **DD-MM-YYYY**.
        - Procure sempre preencher a coluna **Entrega_mensurável** com um resultado concreto.

        Quando terminar, clique em **"Gerar gráfico de Gantt"**.
        """
    )

    # DataFrame inicial de exemplo
    df_inicial = pd.DataFrame({
        "Projeto": ["Exemplo Projeto X", "Exemplo Projeto X"],
        "Tarefa": ["Planejamento experimento", "Coleta de dados"],
        "Início": ["01-02-2025", "15-03-2025"],
        "Fim": ["28-02-2025", "30-04-2025"],
        "Entrega_mensurável": [
            "Documento de protocolo experimental",
            "Banco de dados bruto organizado"
        ]
    })

    df_editado = st.data_editor(
        df_inicial,
        num_rows="dynamic",
        use_container_width=True
    )

    st.markdown("")

    if st.button("Gerar gráfico de Gantt"):
        # Copiar o DataFrame e limpar linhas vazias
        df_manual = df_editado.copy()

        # Remover linhas onde Projeto, Tarefa, Início ou Fim estão vazios
        df_manual = df_manual.dropna(subset=["Projeto", "Tarefa", "Início", "Fim"], how="any")

        if df_manual.empty:
            st.warning("Nenhuma linha válida encontrada. Preencha pelo menos uma atividade.")
        else:
            # Converter datas
            df_manual["Início"] = pd.to_datetime(df_manual["Início"], dayfirst=True, errors="coerce")
            df_manual["Fim"] = pd.to_datetime(df_manual["Fim"], dayfirst=True, errors="coerce")

            df_manual = df_manual.dropna(subset=["Início", "Fim"])

            if df_manual.empty:
                st.error("Todas as datas ficaram inválidas. Verifique o formato (DD-MM-YYYY).")
            else:
                df_g = preparar_df_para_gantt(df_manual)
                st.markdown("### Gráfico de Gantt (dados preenchidos na tela)")
                fig = fig_gantt(df_g, "Cronograma – entrada manual")
                st.plotly_chart(fig, use_container_width=True)

                st.caption(
                    "💾 Para salvar o gráfico como imagem, clique no ícone de **câmera** "
                    "no canto superior direito do gráfico (\"Download plot as png\")."
                )

                with st.expander("Ver dados utilizados para o Gantt"):
                    st.dataframe(df_g)