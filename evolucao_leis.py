
import time
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Evolução dos PLs – Câmara dos Deputados", layout="wide")

# =======================
# Utils
# =======================
@st.cache_data(show_spinner=False, ttl=60*30)
def fetch_all_proposicoes(tipo="PL", ano_ini=2019, ano_fim=2025, itens_por_pagina=100):
    """
    Busca TODAS as proposições via API da CÂMARA (pagina até acabar).
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
                "itens": itens_por_pagina,  # máx 100
                "ordem": "ASC",
                "ordenarPor": "id"
            }
            r = requests.get(base_url, params=params, timeout=30)
            r.raise_for_status()
            j = r.json()

            lst = j.get("dados", [])
            if not lst:
                break

            for d in lst:
                dados.append({
                    "id": d.get("id"),
                    "ano": ano,
                    "siglaTipo": d.get("siglaTipo"),
                    "numero": d.get("numero"),
                    "ementa": d.get("ementa"),
                    "dataApresentacao": d.get("dataApresentacao"),
                    "uriAutores": d.get("uriAutores"),
                })

            links = j.get("links", [])
            tem_next = any(l.get("rel") == "next" for l in links)
            if not tem_next:
                break

            pagina += 1
            time.sleep(0.2)

    df = pd.DataFrame(dados)
    if not df.empty and "dataApresentacao" in df.columns:
        df["dataApresentacao"] = pd.to_datetime(df["dataApresentacao"], errors="coerce")
        df["mes"] = df["dataApresentacao"].dt.to_period("M").astype(str)
    return df


@st.cache_data(show_spinner=False, ttl=60*30)
def fetch_partidos_por_id(ids, limite_autores_por_id=5):
    """
    Para cada proposição (id), chama /proposicoes/{id}/autores e extrai partidos.
    """
    registros = []
    for pid in ids:
        try:
            url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{pid}/autores"
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            j = r.json().get("dados", [])
            for a in j[:limite_autores_por_id]:
                partido = (
                    (a.get("autor") or {}).get("siglaPartido") or
                    a.get("siglaPartidoAutor") or
                    a.get("siglaPartido") or
                    "SEM_PARTIDO"
                )
                registros.append({"id": pid, "partido": partido or "SEM_PARTIDO"})
        except Exception:
            registros.append({"id": pid, "partido": "SEM_PARTIDO"})
        time.sleep(0.05)
    return pd.DataFrame(registros)


# =======================
# UI
# =======================
st.title("📊 Evolução de Projetos de Lei (PL) – Câmara dos Deputados")
st.caption("Fonte dos dados: API de Dados Abertos da **Câmara dos Deputados** (não é o Senado).")

col1, col2, col3 = st.columns([1,1,1])
with col1:
    ano_ini = st.number_input("Ano inicial", 1988, 2025, 2019, step=1)
with col2:
    ano_fim = st.number_input("Ano final", 1988, 2025, 2025, step=1)
with col3:
    tipo = st.selectbox("Tipo da proposição", ["PL", "PEC", "PLP", "PDL"], index=0)

st.divider()

with st.spinner("Carregando proposições da Câmara…"):
    df = fetch_all_proposicoes(tipo=tipo, ano_ini=ano_ini, ano_fim=ano_fim)

if df.empty:
    st.warning("Nenhuma proposição encontrada no intervalo informado.")
    st.stop()

st.success(f"Total de {tipo}s encontrados no período: **{len(df):,}**")

# =======================
# GRÁFICO 1 – Evolução (por mês)
# =======================
st.subheader("📈 Evolução temporal (por mês)")
serie_mes = df.groupby("mes").size().sort_index()
fig1, ax1 = plt.subplots(figsize=(10, 4))
ax1.plot(serie_mes.index, serie_mes.values, marker="o", linewidth=2.2)
ax1.set_xlabel("Mês")
ax1.set_ylabel(f"Qtde de {tipo}s")
ax1.set_title(f"Evolução mensal de {tipo}s ({ano_ini}–{ano_fim})")
ax1.tick_params(axis='x', labelrotation=45)
st.pyplot(fig1)

st.caption("Obs.: A série usa a data de apresentação (`dataApresentacao`).")

st.divider()

# =======================
# GRÁFICO 2 – Por partido (diferente do gráfico 1)
# =======================
st.subheader("🏛️ Distribuição por partido (autoria)")
amostra_max = st.slider("Tamanho da amostra para consulta de autores (evita exceder cota de API)",
                        200, 5000, 1000, step=100)
ids_para_buscar = df["id"].dropna().astype(int).head(amostra_max).tolist()

with st.spinner("Consultando partidos dos autores…"):
    dfp = fetch_partidos_por_id(ids_para_buscar)

if dfp.empty:
    st.info("Não foi possível obter autores nesta amostra. Tente aumentar o limite ou mudar o período.")
else:
    contagem = dfp.groupby("partido").size().sort_values(ascending=False).head(20)
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.bar(contagem.index, contagem.values)
    ax2.set_xlabel("Partido (autoria)")
    ax2.set_ylabel(f"Nº de {tipo}s (amostra)")
    ax2.set_title(f"{tipo}s por partido (top 20 na amostra)")
    ax2.tick_params(axis='x', labelrotation=45)
    st.pyplot(fig2)

st.divider()

with st.expander("🔎 Ver tabela (amostra)"):
    st.dataframe(df[["id", "ano", "numero", "siglaTipo", "dataApresentacao", "ementa"]].head(200),
                 use_container_width=True)
