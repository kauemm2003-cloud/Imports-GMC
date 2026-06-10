import streamlit as st
import pandas as pd
import json
import os

st.set_page_config(page_title="GMC - Diagnóstico", layout="wide")
st.title("🔍 Painel de Diagnóstico de Dados Siscomex")

NOME_ARQUIVO_BANCO = "banco_siscomex.json"

if os.path.exists(NOME_ARQUIVO_BANCO):
    try:
        with open(NOME_ARQUIVO_BANCO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        
        df_siscomex = pd.json_normalize(dados)
        st.success("✅ Arquivo lido com sucesso pelo Python!")
        
        st.subheader("1. Como as colunas estão estruturadas:")
        st.write(df_siscomex.dtypes.astype(str))
        
        st.subheader("2. Amostra real dos seus dados (Primeiras 3 linhas):")
        st.dataframe(df_siscomex.head(3))
        
    except Exception as e:
        st.error(f"Erro crítico na leitura primária: {e}")
else:
    st.warning(f"Arquivo '{NOME_ARQUIVO_BANCO}' não encontrado no GitHub.")
