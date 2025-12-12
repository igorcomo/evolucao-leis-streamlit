import time
import math
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import pandas as pd
import streamlit as st

# -------- SESSÃO COM RETRY E BACKOFF --------
def make_session():
    sess = requests.Session()
    retries = Retry(
        total=5,                 # até 5 tentativas
        backoff_factor=1.2,      # 1.2s, 2.4s, 4.8s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount("https://", adapter)
    sess.headers.update({
        "User-Agent": "FGV-Projeto-P2-IgorCosta/1.0 (contato: email@exemplo.com)",
        "Accept": "application/json"
    })
    return sess

SESSION = make_session()
BASE = "https://dadosabertos.camara.leg.br/api/v2"

def safe_get(url, params=None):
    """GET com tratamento de erro, 429 e fallback.
       Retorna dict ou None (não explode o app)."""
    try:
        resp = SESSION.get(url, params=params, timeout=30)
        # Trata 429 manualmente se ainda acontecer
        if resp.status_code == 429:
            # Respeita Retry-After se vier
            wait = int(resp.headers.get("Retry-After", "2"))
            time.sleep(wait)
            resp = SESSION.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        st.warning(f"Servidor retornou {resp.status_code} em {url}. "
                   "Vou tentar continuar com dados parciais.")
        return None
    except Exception as e:
        st.warning(f"Falha ao acessar {url}: {e}. Continuando com dados parciais.")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def buscar_pls_periodo(ano_ini: int, ano_fim: int):
    """Paginação completa: coleta TODOS os PLs do período (dados básicos)."""
    todos = []
    for ano in range(ano_ini, ano_fim + 1):
        pagina = 1
        while True:
            params = {
                "siglaTipo": "PL",
                "dataApresentacaoInicio": f"{ano}-01-01",
                "dataApresentacaoFim": f"{ano}-12-31",
                "itens": 100,
                "pagina": pagina
            }
            js = safe_get(f"{BASE}/proposicoes", params)
            if not js:
                break
            dados = js.get("dados", [])
            todos.extend(dados)
            # segue paginação pelo link "next"
            links = {l["rel"]: l["href"] for l in js.get("links", [])}
            if "next" in links and len(dados) > 0:
                pagina += 1
                # pequena pausa para não estourar limite
                time.sleep(0.15)
            else:
                break
    df = pd.DataFrame(todos)
    # garante colunas esperadas:
    if "dataApresentacao" in df.columns:
        df["dataApresentacao"] = pd.to_datetime(df["dataApresentacao"], errors="coerce")
        df["ano_mes"] = df["dataApresentacao"].dt.to_period("M").astype(str)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def autores_por_proposicao(id_proposicao: int):
    """Busca autores para 1 proposição (retorna lista de dicts)."""
    js = safe_get(f"{BASE}/proposicoes/{id_proposicao}/autores")
    if not js:
        return []
    return js.get("dados", [])

def contar_autores_por_partido(df_pl: pd.DataFrame, limitar=None):
    """Conta autores parlamentares por partido. Pode limitar nº de PLs para modo rápido."""
    partidos = []
    # opcional: limitar quantidade de proposições para acelerar
    ids = df_pl["id"].dropna().astype(int).tolist()
    if limitar:
        ids = ids[:limitar]

    for i, pid in enumerate(ids, start=1):
        # espaçar as chamadas um pouco:
        if i % 25 == 0:
            time.sleep(0.4)
        autores = autores_por_proposicao(pid)
        for a in autores:
            # filtra só parlamentares (tipoAutor pode variar)
            if a.get("tipoAutor", "").lower().startswith("parlamentar"):
                partido = a.get("partido", "") or a.get("siglaPartidoAutor", "")
                if partido:
                    partidos.append(partido)
    s = pd.Series(partidos, dtype="string")
    if s.empty:
        return pd.DataFrame(columns=["partido", "autores"])
    cont = s.value_counts().rename_axis("partido").reset_index(name="autores")
    cont = cont.sort_values("autores", ascending=False)
    return cont
