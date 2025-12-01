import time
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ----------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# ----------------------------------------------------------
st.set_page_config(
    page_title="Evolução dos Projetos de Lei – Câmara dos Deputados",
    layout="wide"
)

st.title("📊 Evolução de Projetos de Lei (PL) – Câmara dos Deputados")
st.caption("Fonte dos dados: API de Dados Abertos da **Câmara dos Deputados**. (Correção do professor)")


# ==========================================================
# FUNÇÃO OTIMIZADA PARA BUSCAR PROPOSIÇÕES
# – Sem paginação (muito mais rápido)
# – Apenas 1 requisição por ano
# – Cache de 24h
# ==========================================================
@st.cache_data(show_spinner=False, ttl=60*60*24)
def fetch_proposicoes(tipo="PL", ano_ini=2019, ano_fim=2025):
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
    dados = []

    for ano in range(ano_ini, ano_fim + 1):
        params = {
            "siglaTipo": tipo,
            "ano": ano,
            "itens": 1000,      # Tenta puxar o máximo possível de uma vez
            "ordem": "ASC",
            "ordenarPor": "id"
        }

        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            lista = r.json().get("dados", [])

            for d in lista:
                dados.append({
                    "id": d.get("id"),
                    "ano": ano,
                    "numero": d.get("numero"),
                    "siglaTipo": d.get("siglaTipo"),
                    "ementa": d.get("ementa"),
                    "dataApresentacao": d.get("dataApresentacao"),
                    "uriAutores": d.get("uriAutores")
                })

        except Exception:
            pass

        time.sleep(0.2)

    df = pd.DataFrame(dados)

    if not df.empty:
        df["dataApresentacao"] = pd.to_datetime(df["dataApresentacao"], errors="coerce")
        df["mes"] = df["dataApresentacao"].dt.to_period("M").astype(str)

    return df


# ==========================================================
# BUSCA DE PARTIDOS (AUTORIA)
# – Agora usa amostragem e não consulta todos os PLs
# – Muito mais rápido e leve
# ==========================================================
@st.cache_data(show_spinner=False, ttl=60*60*24)
def buscar_partidos(ids):
    registros = []
    for pid in ids:
        try:
            url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{pid}/autores"
            r = requests.get(url, timeout=15)
            r.raise_for_status()

            autores = r.json().get("dados", [])
            for a in autores[:3]:  # limita a 3 autores por PL
                partido = (
                    (a.get("autor") or {}).get("siglaPartido")
                    or a.get("siglaPartidoAutor")
                    or "SEM_PARTIDO"
                )
                registros.append({"id": pid, "partido": partido})

        except Exception:
            registros.append({"id": pid, "partido": "SEM_PARTIDO"})

        time.sleep(0.05)

    return pd.DataFrame(registros)


# ----------------------------------------------------------
# INTERFACE – PARÂMETROS DO USUÁRIO
# ----------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    ano_ini = st.number_input("Ano inicial", 1988, 2025, 2019)
with col2:
    ano_fim = st.number_input("Ano final", 1988, 2025, 2023)
with col3:
    tipo = st.selectbox("Tipo da proposição", ["PL", "PEC", "PLP", "PDL"])

st.divider()

with st.spinner("Carregando dados da Câmara dos Deputados..."):
    df = fetch_proposicoes(tipo, ano_ini, ano_fim)

if df.empty:
    st.error("Nenhuma proposição encontrada no período selecionado.")
    st.stop()

st.success(f"Foram encontrados **{len(df):,} {tipo}s** no período selecionado.")


# ==========================================================
# GRÁFICO 1 – EVOLUÇÃO TEMPORAL (mensal)
# ==========================================================
st.subheader("📈 Evolução Temporal")

serie = df.groupby("mes").size().sort_index()

fig1, ax1 = plt.subplots(figsize=(10, 4))
ax1.plot(serie.index, serie.values, marker="o", linewidth=2.5, color="#48C9B0")
ax1.fill_between(serie.index, serie.values, color="#48C9B0", alpha=0.3)

ax1.set_title(f"Evolução mensal de {tipo}s ({ano_ini}–{ano_fim})")
ax1.set_xlabel("Mês")
ax1.set_ylabel("Quantidade")
ax1.tick_params(axis="x", rotation=45)

st.pyplot(fig1)
st.caption("A série temporal usa a **data de apresentação** oficial registrada.")


st.divider()

# ==========================================================
# GRÁFICO 2 – DISTRIBUIÇÃO POR PARTIDO
# ==========================================================
st.subheader("🏛️ Distribuição por Partido (Autoria)")

# amostragem automática adaptada ao tamanho do dataset
tamanho_amostra = min(600, len(df))

ids = df["id"].dropna().sample(tamanho_amostra, random_state=42).tolist()

with st.spinner(f"Coletando autores de {tamanho_amostra} proposições (amostra)..."):
    dfp = buscar_partidos(ids)

if dfp.empty:
    st.warning("Não foi possível obter autores nesta amostra.")
else:
    contagem = dfp.groupby("partido").size().sort_values(ascending=False).head(20)

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.bar(contagem.index, contagem.values, color="#5DADE2")
    ax2.set_title(f"Top partidos que mais apresentaram {tipo}s (amostra)")
    ax2.set_xlabel("Partido")
    ax2.set_ylabel("Quantidade")
    ax2.tick_params(axis="x", rotation=45)

    st.pyplot(fig2)

st.divider()

with st.expander("📄 Ver tabela completa (primeiras 200 linhas)"):
    st.dataframe(
        df[["id", "ano", "numero", "siglaTipo", "dataApresentacao", "ementa"]].head(200),
        use_container_width=True
    )
