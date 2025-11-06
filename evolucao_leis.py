
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Título e descrição
st.title("📜 Evolução das Leis Federais no Brasil (1822–2025)")
st.write("""
Este gráfico mostra a evolução histórica da produção legislativa brasileira, 
medida em número de leis federais promulgadas por década.
""")

# Dataset
data = {
    "Década": ["1820–1830", "1830–1840", "1850–1860", "1870–1880", "1890–1900",
               "1910–1920", "1930–1940", "1950–1960", "1970–1980", "1980–1990",
               "1990–2000", "2000–2010", "2010–2020", "2020–2025"],
    "Leis Promulgadas": [15, 40, 55, 70, 110, 150, 300, 450, 600, 900, 1200, 1600, 2000, 850]
}
df = pd.DataFrame(data)

# Gráfico
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df["Década"], df["Leis Promulgadas"], marker="o", linewidth=2.5, color="#4C9F70")
ax.fill_between(df["Década"], df["Leis Promulgadas"], color="#4C9F70", alpha=0.3)
ax.set_title("Evolução da Legislação Brasileira", fontsize=16, fontweight="bold")
ax.set_xlabel("Década")
ax.set_ylabel("Número de Leis Promulgadas")

# Anotação histórica
ax.annotate("Constituição de 1988", xy=(9, 900), xytext=(8.2, 1300),
            arrowprops=dict(arrowstyle="->", color="gray"), fontsize=10, color="white")

st.pyplot(fig)
st.caption("Fonte: Dados simulados com base em estimativas históricas do Senado Federal.")
