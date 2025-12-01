import time
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Evolução dos PLs – Câmara dos Deputados", layout="wide")

# =======================
# FUNÇÕES DE BUSCA
# =======================
@st.cache_data(show_spinner=False, ttl=60*30)
def fetch_all_proposicoes(tipo="PL", ano_ini=2019, ano_fim=2025):
    """
    Busca TODAS as proposições da Câmara, com paginação.
    """
    base_url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
    dados = []

    for ano in range(ano_ini, ano_fim + 1):
        pagina = 1
        while True:
            params = {
                "siglaTipo": tipo,
                "ano": ano,
                "pagina": pagina,
                "itens": 100,
                "ordem": "ASC",
                "ordenarPor": "id"
            }
            r = requests.get(base_url, params=params, timeout=60)
            if r.status_code != 200:
                break
            j = r.json()
            lista = j.get("dados", [])
            if not lista:
                break
            for d in lista:
                dados.append({
                    "id": d.get("id"),
                    "ano": ano,
                    "siglaTipo": d.get("siglaTipo"),
                    "numero": d.get("numero"),
                    "ementa": d.get("ementa"),
                    "dataApresentacao": d.get("dataApresentacao"),
                    "uriAutores": d.get("uriAutores")
                })
            if not any(l.get("rel") == "next" for l in j.get("links", [])):
                break
            pagina += 1
            time.sleep(0.3)
    df = pd.DataFrame(dados)
    if not df.empty:
        df["dataApresentacao"] = pd.to_datetime(df["dataApresentacao"], errors="coerce")
        df["mes"] = df["dataApresentacao"].dt.to_period("M").astype(str)
    return df


@st.cache_data(show_spinner=False, ttl=60*30)
def fetch_partidos_por_id(ids):
    """
    Para cada proposição, coleta até 5 autores e seus partidos.
    """
    registros = []
    for pid in ids:
        try:
            url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{pid}/autores"
            r = requests.get(url, timeout=30)
            j = r.json().get("dados", [])
            for a in j[:5]:
                partido = (
                    (a.get("autor") or {}).get("siglaPartido") or
                    a.get("siglaPartidoAutor") or
                    a.get("siglaPartido") or
                    "SEM_PARTIDO"
                )
                registros.append({"id": pid, "partido": partido})
        except:
            registros.append({"id": pid, "partido": "SEM_PARTIDO"})
        time.sleep(0.1)
    return pd.DataFrame(registros)

# =======================
# INTERFACE
# =======================
st.title("📊 Evolução de Projetos de Lei (PL) – Câmara dos Deputados")
st.caption("Fonte dos dados: API de Dados Abertos da **Câmara dos Deputados** (não é o Senado).")

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    ano_ini = st.number_input("Ano inicial", 1988, 2025, 2019, step=1)
with col2:
    ano_fim = st.number_input("Ano final", 1988, 2025, 2025, step=1)
with col3:
    tipo = st.selectbox("Tipo da proposição", ["PL", "PEC", "PLP", "PDL"], index=0)

st.divider()

with st.spinner("Carregando proposições da Câmara..."):
    df = fetch_all_proposicoes(tipo, ano_ini, ano_fim)

if df.empty:
    st.warning("Nenhuma proposição encontrada no intervalo informado.")
    st.stop()

st.success(f"Foram encontradas **{len(df):,} {tipo}s** no período de {ano_ini} a {ano_fim}.")

# =======================
# GRÁFICO 1 – EVOLUÇÃO TEMPORAL
# =======================
st.subheader("📈 Evolução Temporal")
serie = df.groupby("mes").size().sort_index()
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(serie.index, serie.values, marker="o", color="#4C9F70")
ax.fill_between(serie.index, serie.values, color="#A2D9A2", alpha=0.5)
ax.set_xlabel("Mês")
ax.set_ylabel("Quantidade de PLs")
ax.set_title(f"Evolução mensal de {tipo}s ({ano_ini}–{ano_fim})")
plt.xticks(rotation=45)
st.pyplot(fig)

# =======================
# GRÁFICO 2 – DISTRIBUIÇÃO POR PARTIDO
# =======================
st.subheader("🏛️ Distribuição por Partido (autores)")
amostra = st.slider("Quantidade de PLs na amostra (para evitar limite da API)", 100, 3000, 1000, step=100)
ids = df["id"].dropna().astype(int).head(amostra).tolist()

with st.spinner("Consultando autores..."):
    df_part = fetch_partidos_por_id(ids)

if df_part.empty:
    st.info("Não foi possível obter autores nesta amostra.")
else:
    contagem = df_part["partido"].value_counts().head(15)
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.bar(contagem.index, contagem.values, color="#6699CC")
    ax2.set_xlabel("Partido")
    ax2.set_ylabel("Quantidade de PLs")
    ax2.set_title(f"Top 15 partidos com mais {tipo}s ({ano_ini}–{ano_fim})")
    plt.xticks(rotation=45)
    st.pyplot(fig2)

st.divider()
with st.expander("📋 Ver dados brutos (amostra)"):
    st.dataframe(df[["id", "ano", "numero", "siglaTipo", "dataApresentacao", "ementa"]].head(300))
