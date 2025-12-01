# 📊 Aplicação Web – Geração de Gráficos de Gantt para Projetos de Pesquisa

Esta aplicação permite que pesquisadores criem **gráficos de Gantt interativos** para seus projetos de pesquisa, a partir de:

- **Planilhas Excel** (uma aba por pesquisador ou uma aba única), ou  
- **Entrada manual** diretamente pela interface (“sem Excel”), usando um editor de tabela interativo.

A aplicação está disponível online via **Streamlit Cloud**, e pode ser rodada também localmente.
---

## 🌐 Como acessar a aplicação online

Se a aplicação estiver publicada no Streamlit Community Cloud, o link aparecerá aqui:

👉 **[Acesse a aplicação online](INSERIR_LINK_AQUI)**  
*(Substitua pelo link gerado pelo Streamlit Cloud.)*

---

## 🚀 Funcionalidades

### ✔️ Duas formas de inserção de dados
1. **Upload de planilha Excel (.xlsx)**  
   - Uma aba por pesquisador ou uma única aba.  
   - Colunas obrigatórias:  
     - `Projeto`  
     - `Tarefa`  
     - `Início` (formato DD-MM-YYYY)  
     - `Fim` (formato DD-MM-YYYY)  
   - Coluna recomendada:  
     - `Entrega_mensurável`  

2. **Preenchimento manual**  
   - Tabela editável usando `st.data_editor`  
   - Adição/remoção de linhas dinâmicas  
   - Preenchimento de datas, atividade e entrega  
   - Geração instantânea do Gantt

---

## 📘 Sobre entregas mensuráveis

Cada atividade do cronograma deve ter **um resultado concreto**, por exemplo:

| Atividade | Entrega mensurável |
|-----------|--------------------|
| Revisão da literatura | Lista organizada de referências / documento de revisão |
| Coleta de dados | Banco de dados organizado (CSV/Excel) |
| Análise preliminar | Notebook com análises exploratórias |
| Redação | Rascunho da seção correspondente |

Isso ajuda a manter clareza, permite avaliar progresso e conecta atividades operacionais com resultados verificáveis.

---

## 📄 Exemplo de planilha

Este repositório contém um exemplo de planilha chamada:

```
exemplo_cronograma.xlsx
```

Ela demonstra o formato esperado e pode ser usada como modelo pelos pesquisadores.

---

## 🗂 Estrutura do repositório

```
├── app_gantt_lab.py           # Aplicação Streamlit
├── requirements.txt           # Dependências
├── exemplo_cronograma.xlsx    # Exemplo de planilha
└── README.md                  # Este arquivo
```

## 💻 Executar localmente

### Pré-requisitos

- Python 3.9+
- pip
- Bibliotecas listadas no `requirements.txt`

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Rodar a aplicação localmente

```bash
streamlit run app_gantt_lab.py
```

A aplicação abrirá automaticamente no navegador em:

```
http://localhost:8501
```

---

## ☁️ Como fazer deploy via GitHub + Streamlit Cloud

1. Faça um fork ou clone deste repositório.  
2. Suba para a sua conta GitHub.  
3. Acesse: https://streamlit.io/cloud  
4. Conecte sua conta GitHub.  
5. Clique em **New App** → selecione este repositório.  
6. Configure:
   - **Main file**: `app_gantt_lab.py`  
   - **Branch**: `main`  
   - **Python version**: sugerida pelo Streamlit  
7. Clique em **Deploy**.

Pronto — sua aplicação estará disponível publicamente.

---

## 🛠 Próximas melhorias (sugestões)

- Exportação do Gantt direto para PDF.  
- Inclusão de cores customizáveis por projeto.  
- Gantt por pesquisador + visão geral com timeline alinhada.  
- Autenticação (login) para uso interno do laboratório.  
- Armazenamento de cronogramas em banco de dados.

---

## 📬 Suporte / Contato

Se precisar de ajuda, sugestões ou quiser estender a aplicação, abra uma **issue** neste repositório.
