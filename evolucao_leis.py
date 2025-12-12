import time
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

BASE = "https://dadosabertos.camara.leg.br/api/v2"

# ---------- UTIL: paginação robusta seguindo "links.next" ----------
def _get_all_pages(url, params):
    """Segue o link 'next' devolvido pela API até acabar."""
    out = []
    while True:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        out.extend(j.get("dados", []))

        # acha "next" na lista de links
        links = j.get("links", [])
        next_url = None
        for lk in links:
            if lk.get("rel") == "next":
                next_url = lk.get("href")
                break

        if not next_url:
            break

        # quando existe next, zera params e segue para o href completo
        url, params = next_url, None
        time.sleep(0.15)
    return out

@st.cache_data(show_spinner=False, ttl=60*20)
def fetch_proposicoes_intervalo(ano_ini: int, ano_fim: int, tipo="PL"):
    """Busca TODAS as proposições do intervalo, ano a ano, com paginação total."""
    rows = []
    for ano in range(ano_ini, ano_fim + 1):
        params = {
            "tipo": tipo,
            "dataApresentacaoIni": f"{ano}-01-01",
            "dataApresentacaoFim": f"{ano}-12-31",
            "ordem": "ASC",
            "ordenarPor": "id",
            "itens": 100  # a API ignora além de 100; o resto vem via links.next
        }
        dados = _get_all_pages(f"{BASE}/proposicoes", params)
        rows.extend(dados)
        time.sleep(0.2)

    df = pd.DataFrame(rows).drop_duplicates(subset=["id"])
    if "dataApresentacao" in df.columns:
        df["dataApresentacao"] = pd.to_datetime(df["dataApresentacao"], errors="coerce")
        df["ano_mes"] = df["dataApresentacao"].dt.to_period("M").astype(str)
        df["ano"] = df["dataApresentacao"].dt.year
    return df

@st.cache_data(show_spinner=False, ttl=60*20)
def fetch_partidos_todos(ids, show_progress=True):
    """Para TODOS os ids informados, soma partidos dos autores parlamentares."""
    cont = {}
    progress = st.progress(0) if show_progress else None
    total = len(ids)
    for i, pid in enumerate(ids, 1):
        try:
            r = requests.get(f"{BASE}/proposicoes/{pid}/autores", timeout=30)
            r.raise_for_status()
            for a in r.json().get("dados", []):
                if a.get("tipoAutor") == "Parlamentar":
                    sigla = a.get("siglaPartidoAutor") or a.get("siglaPartido") or "SEM_PARTIDO"
                    sigla = (sigla or "").strip() or "SEM_PARTIDO"
                    cont[sigla] = cont.get(sigla, 0) + 1
        except Exception:
            pass
        if progress and i % 20 == 0:
            progress.progress(min(i/total, 1.0))
        time.sleep(0.08)  # respeita limites e evita 429

    if progress:
        progress.progress(1.0)

    dfp = pd.DataFrame([{"partido": k, "qtd": v} for k, v in cont.items()])
    if not dfp.empty:
        dfp = dfp.sort_values("qtd", ascending=False).reset_index(drop=True)
    return dfp

# ---------- Gráficos ----------
def grafico_evolucao(df):
    if df.empty:
        st.info("Sem dados para o período.")
        return
    serie = df.groupby("ano_mes")["id"].count()
    fig, ax = plt.subplots()
    ax.plot(serie.index, serie.values, marker="o")
    ax.set_title("Evolução Mensal de PLs (Apresentação)")
    ax.set_xlabel("Ano-Mês"); ax.set_ylabel("Quantidade de PLs")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)

def grafico_por_partido(df, usar_todos=True, limite=None):
    if df.empty:
        st.info("Sem dados para o período.")
        return
    ids = df["id"].tolist()
    if not usar_todos and limite:
        ids = ids[:limite]  # opção caso você queira demonstrar rápido

    dfp = fetch_partidos_todos(ids, show_progress=True)
    if dfp.empty:
        st.info("Não foi possível recuperar partidos dos autores.")
        return

    top = st.slider("TOP N partidos:", 5, max(5, min(30, len(dfp))), 12)
    fig, ax = plt.subplots()
    ax.bar(dfp.head(top)["partido"], dfp.head(top)["qtd"])
    ax.set_title("Proposições por Partido (Autores)")
    ax.set_xlabel("Partido"); ax.set_ylabel("Quantidade")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)

# ---------- UI ----------
st.title("📜 Evolução das Proposições – Câmara dos Deputados (API Oficial)")

col1, col2 = st.columns(2)
with col1:
    ano_ini = st.number_input("Ano inicial", min_value=1991, max_value=2025, value=2019, step=1)
with col2:
    ano_fim = st.number_input("Ano final", min_value=1991, max_value=2025, value=2025, step=1)

if ano_ini > ano_fim:
    st.error("O ano inicial não pode ser maior que o ano final.")
    st.stop()

st.caption("Fonte: https://dadosabertos.camara.leg.br/ (proposições e autores)")

usar_todos = st.toggle("Usar TODOS os PLs para o gráfico por partido (lento, mas completo)", value=True)
if not usar_todos:
    limite = st.number_input("Opcional: limite de PLs (para testes rápidos)", 100, 5000, 1500, step=100)
else:
    limite = None

if st.button("Atualizar dados"):
    with st.spinner("Buscando proposições (página por página)…"):
        df = fetch_proposicoes_intervalo(ano_ini, ano_fim, tipo="PL")
    st.success(f"Total no período: {len(df):,}".replace(",", "."))

    st.subheader("Gráfico 1 – Evolução Mensal (Apresentação)")
    grafico_evolucao(df)

    st.subheader("Gráfico 2 – Distribuição por Partido (Autores)")
    grafico_por_partido(df, usar_todos=usar_todos, limite=limite)
