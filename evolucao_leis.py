import time
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

BASE = "https://dadosabertos.camara.leg.br/api/v2"

@st.cache_data(show_spinner=False, ttl=60*30)
def fetch_proposicoes(ano_ini: int, ano_fim: int, tipo="PL"):
    """Busca TODAS as proposições do período, com paginação (100 por página)."""
    itens = 100
    pagina = 1
    rows = []

    while True:
        params = {
            "tipo": tipo,
            "dataApresentacaoIni": f"{ano_ini}-01-01",
            "dataApresentacaoFim": f"{ano_fim}-12-31",
            "ordem": "ASC",
            "ordenarPor": "id",
            "itens": itens,
            "pagina": pagina,
        }
        r = requests.get(f"{BASE}/proposicoes", params=params, timeout=30)
        r.raise_for_status()
        data = r.json().get("dados", [])
        if not data:
            break
        rows.extend(data)
        pagina += 1
        time.sleep(0.2)  # respeitar limites

    df = pd.DataFrame(rows)
    # Garantir coluna dataApresentacao no formato data
    if "dataApresentacao" in df.columns:
        df["dataApresentacao"] = pd.to_datetime(df["dataApresentacao"], errors="coerce")
        df["ano_mes"] = df["dataApresentacao"].dt.to_period("M").astype(str)
        df["ano"] = df["dataApresentacao"].dt.year
    return df

@st.cache_data(show_spinner=False, ttl=60*30)
def fetch_partidos_por_proposicoes(ids):
    """Para cada proposição, busca autores e retorna contagem de siglaPartido."""
    cont = {}
    for pid in ids:
        try:
            r = requests.get(f"{BASE}/proposicoes/{pid}/autores", timeout=30)
            r.raise_for_status()
            autores = r.json().get("dados", [])
            for a in autores:
                # Considerar apenas parlamentares
                if a.get("tipoAutor") == "Parlamentar":
                    sigla = a.get("siglaPartidoAutor") or a.get("siglaPartido") or "SEM_PARTIDO"
                    sigla = (sigla or "").strip() or "SEM_PARTIDO"
                    cont[sigla] = cont.get(sigla, 0) + 1
            time.sleep(0.15)
        except Exception:
            # em caso de erro pontual nessa proposição, segue
            continue
    dfp = pd.DataFrame([{"partido": k, "qtd": v} for k, v in cont.items()])
    if not dfp.empty:
        dfp = dfp.sort_values("qtd", ascending=False).reset_index(drop=True)
    return dfp

def grafico_evolucao(df):
    """Gráfico 1: Evolução mensal (ano-mês) de apresentação de PLs."""
    if df.empty:
        st.info("Sem dados para o período.")
        return
    serie = df.groupby("ano_mes")["id"].count()
    fig, ax = plt.subplots()
    ax.plot(serie.index, serie.values, marker="o")
    ax.set_title("Evolução Mensal de PLs (Apresentação)")
    ax.set_xlabel("Ano-Mês")
    ax.set_ylabel("Quantidade de PLs")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)

def grafico_por_partido(df):
    """Gráfico 2: Distribuição por partido (autores)."""
    if df.empty:
        st.info("Sem dados para o período.")
        return
    ids = df["id"].tolist()
    # Para performance, limitar a, por exemplo, 1500 proposições (ajuste se quiser)
    ids = ids[:1500]
    dfp = fetch_partidos_por_proposicoes(ids)
    if dfp.empty:
        st.info("Não foi possível recuperar partidos dos autores.")
        return

    top = st.slider("Quantos partidos exibir (TOP N)?", 5, min(20, len(dfp)), 10)
    dfp_top = dfp.head(top)

    fig, ax = plt.subplots()
    ax.bar(dfp_top["partido"], dfp_top["qtd"])
    ax.set_title("Proposições por Partido (Autores)")
    ax.set_xlabel("Partido")
    ax.set_ylabel("Quantidade")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)

# ------------------ UI ------------------

st.title("📜 Evolução das Leis Federais – Câmara dos Deputados")

col1, col2 = st.columns(2)
with col1:
    ano_ini = st.number_input("Ano inicial", min_value=1991, max_value=2025, value=2019, step=1)
with col2:
    ano_fim = st.number_input("Ano final", min_value=1991, max_value=2025, value=2025, step=1)

if ano_ini > ano_fim:
    st.error("O ano inicial não pode ser maior que o ano final.")
    st.stop()

st.caption("Fonte: API de Dados Abertos da Câmara dos Deputados")
if st.button("Atualizar dados"):
    with st.spinner("Buscando dados com paginação…"):
        df = fetch_proposicoes(ano_ini, ano_fim, tipo="PL")
    st.success(f"Total de proposições encontradas no período: {len(df)}")

    st.subheader("Gráfico 1 – Evolução Mensal (Apresentação)")
    grafico_evolucao(df)

    st.subheader("Gráfico 2 – Distribuição por Partido (Autores)")
    grafico_por_partido(df)
