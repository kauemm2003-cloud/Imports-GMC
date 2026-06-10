import streamlit as st
import pandas as pd
import json
import os
import re

# Configuração da página do aplicativo
st.set_page_config(page_title="GMC - Siscomex & Invoice Auditor", layout="wide")

st.title("📊 GMC - Sistema de Auditoria e Consulta Siscomex")
st.write("Versão 3.1 - Bug de Digitação Corrigido")

NOME_ARQUIVO_BANCO = "banco_siscomex.json"
df_siscomex = None

# FUNÇÃO AUXILIAR: Formata o NCM (ex: 85363090) para o padrão com pontos (8536.30.90)
def formatar_ncm(ncm_sujo):
    ncm_limpo = re.sub(r'\D', '', str(ncm_sujo))
    if len(ncm_limpo) == 8:
        return f"{ncm_limpo[:4]}.{ncm_limpo[4:6]}.{ncm_limpo[6:]}"
    return ncm_sujo

# FUNÇÃO AUXILIAR: Limpa colchetes, aspas, espaços e converte listas para texto simples
def limpar_campo_complexo(valor):
    if pd.isna(valor):
        return ""
    # Se o valor veio como uma lista do JSON (ex: ['IP.FN2090606']), pega o primeiro item
    if isinstance(valor, list):
        if len(valor) > 0:
            valor = valor[0]
        else:
            return ""
    texto = str(valor)
    texto_limpo = re.sub(r"[\[\]'\" ]", "", texto)
    return texto_limpo

# CARREGAMENTO DO BANCO DE DADOS FIXO COM TRATAMENTO SEGURO
if os.path.exists(NOME_ARQUIVO_BANCO):
    try:
        with open(NOME_ARQUIVO_BANCO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        
        # Se os dados vierem envelopados em uma chave do portal, tentamos extrair a lista
        if isinstance(dados, dict):
            for chave in ['dados', 'itens', 'resultado', 'data']:
                if chave in dados and isinstance(dados[chave], list):
                    dados = dados[chave]
                    break
        
        # Cria o DataFrame bruto
        df_bruto = pd.DataFrame(dados)
        
        # MAPEAMENTO DAS COLUNAS REAIS 
        colunas_necessarias = {}
        for col in df_bruto.columns:
            col_lower = col.lower()
            if 'codigosinterno' in col_lower or 'codigointerno' in col_lower:
                colunas_necessarias['codigosInterno'] = col # ERRO CORRIGIDO AQUI
            elif 'codigo' in col_lower and 'interno' not in col_lower:
                colunas_necessarias['codigo'] = col
            elif 'ncm' in col_lower:
                colunas_necessarias['ncm'] = col
            elif 'descricao' in col_lower or 'product' in col_lower:
                colunas_necessarias['descricao'] = col
            elif 'situacao' in col_lower or 'status' in col_lower:
                colunas_necessarias['situacao'] = col

        # Se encontrou as colunas, monta a tabela limpa
        if colunas_necessarias:
            df_limpo = pd.DataFrame()
            if 'codigosInterno' in colunas_necessarias:
                df_limpo['codigosInterno'] = df_bruto[colunas_necessarias['codigosInterno']].apply(limpar_campo_complexo)
            if 'codigo' in colunas_necessarias:
                df_limpo['codigo'] = df_bruto[colunas_necessarias['codigo']].apply(limpar_campo_complexo).str.zfill(10)
            if 'ncm' in colunas_necessarias:
                df_limpo['ncm'] = df_bruto[colunas_necessarias['ncm']].apply(limpar_campo_complexo).apply(formatar_ncm)
            if 'descricao' in colunas_necessarias:
                df_limpo['descricao'] = df_bruto[colunas_necessarias['descricao']].astype(str).str.strip()
            if 'situacao' in colunas_necessarias:
                df_limpo['situacao'] = df_bruto[colunas_necessarias['situacao']].astype(str).str.strip()
            
            df_siscomex = df_limpo
            st.sidebar.success("✅ Banco Siscomex carregado e tratado com sucesso!")
        else:
            st.sidebar.error("❌ Não foram encontradas as colunas de Código ou NCM no JSON.")
            
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o banco de dados: {e}")
else:
    st.sidebar.warning(f"⚠️ Arquivo '{NOME_ARQUIVO_BANCO}' não encontrado no GitHub.")

# CRIAÇÃO DAS ABAS
aba_auditoria, aba_consulta = st.tabs(["🔍 Validar Nova Invoice", "📋 Consultar Catálogo"])

# -------------------------------------------------------------------------
# ABA 1: VALIDAR NOVA INVOICE
# -------------------------------------------------------------------------
with aba_auditoria:
    st.header("Análise de Commercial Invoice")
    st.write("O sistema lerá apenas até as linhas de itens válidos e fará o cruzamento perfeito.")
    
    arquivo_invoice = st.file_uploader("Suba o arquivo Excel da Invoice", type=["xlsx", "xls"])
    
    if arquivo_invoice is not None and df_siscomex is not None:
        df_invoice = pd.read_excel(arquivo_invoice, skiprows=13, nrows=80, dtype={'COD': str, 'NCM': str})
        df_invoice = df_invoice.dropna(subset=['COD'])
        
        df_invoice['COD'] = df_invoice['COD'].astype(str).str.strip()
        df_invoice['NCM'] = df_invoice['NCM'].apply(formatar_ncm)
        
        # CRUZAMENTO DOS DADOS 
        df_resultado = pd.merge(
            df_invoice, 
            df_siscomex[['codigosInterno', 'codigo', 'ncm', 'descricao', 'situacao']], 
            left_on='COD', 
            right_on='codigosInterno', 
            how='left',
            suffixes=('_invoice', '_siscomex')
        )
        
        def definir_status(
