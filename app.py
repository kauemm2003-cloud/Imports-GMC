import streamlit as st
import pandas as pd
import json
import os
import re

# Configuração da página do aplicativo
st.set_page_config(page_title="GMC - Siscomex & Invoice Auditor", layout="wide")

st.title("📊 GMC - Sistema de Auditoria e Consulta Siscomex")
st.write("Versão 3.2 - Proteção Antifalhas de Cópia Ativada")

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
    if isinstance(valor, list):
        if len(valor) > 0: valor = valor[0]
        else: return ""
    texto = str(valor)
    return re.sub(r"[\[\]'\" ]", "", texto)

# CARREGAMENTO DO BANCO DE DADOS FIXO COM TRATAMENTO SEGURO
if os.path.exists(NOME_ARQUIVO_BANCO):
    try:
        with open(NOME_ARQUIVO_BANCO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        
        if isinstance(dados, dict):
            for chave in ['dados', 'itens', 'resultado', 'data']:
                if chave in dados and isinstance(dados[chave], list):
                    dados = dados[chave]
                    break
        
        df_bruto = pd.DataFrame(dados)
        colunas_necessarias = {}
        
        for col in df_bruto.columns:
            col_lower = col.lower()
            if 'codigosinterno' in col_lower or 'codigointerno' in col_lower:
                colunas_necessarias['codigosInterno'] = col
            elif 'codigo' in col_lower and 'interno' not in col_lower:
                colunas_necessarias['codigo'] = col
            elif 'ncm' in col_lower:
                colunas_necessarias['ncm'] = col
            elif 'descricao' in col_lower or 'product' in col_lower:
                colunas_necessarias['descricao'] = col
            elif 'situacao' in col_lower or 'status' in col_lower:
                colunas_necessarias['situacao'] = col

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
            st.sidebar.error("❌ Não foram encontradas as colunas necessárias no JSON.")
            
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
        
        # LINHA BLINDADA: Tudo em uma única linha para evitar erros de parênteses na cópia
        df_resultado = pd.merge(df_invoice, df_siscomex[['codigosInterno', 'codigo', 'ncm', 'descricao', 'situacao']], left_on='COD', right_on='codigosInterno', how='left', suffixes=('_invoice', '_siscomex'))
        
        def definir_status(row):
            if pd.isna(row['codigosInterno']) or str(row['codigosInterno']).strip() == "" or str(row['codigosInterno']) == 'nan':
                return "🚨 Cadastrar no Siscomex"
            elif row['NCM'] != row['ncm']:
                return "⚠️ Divergência de NCM"
            else:
                return "✅ Tudo Certo"
                
        df_resultado['Status Auditoria'] = df_resultado.apply(definir_status, axis=1)
        
        colunas_exibicao = [c for c in ['ITEM', 'COD', 'NCM', 'PRODUCT DESCRIPTION', 'QTY', 'codigo', 'ncm', 'Status Auditoria'] if c in df_resultado.columns]
        
        status_selecionado = st.multiselect("Filtrar por Status de Auditoria:", options=df_resultado['Status Auditoria'].unique(), default=df_resultado['Status Auditoria'].unique())
        
        df_filtrado = df_resultado[df_resultado['Status Auditoria'].isin(status_selecionado)]
        st.dataframe(df_filtrado[colunas_exibicao], use_container_width=True)
        
    elif df_siscomex is None:
        st.info("Aguardando o arquivo de banco de dados no GitHub para habilitar a auditoria.")

# -------------------------------------------------------------------------
# ABA 2: INTERFACE DE CONSULTA
# -------------------------------------------------------------------------
with aba_consulta:
    st.header("Busca Rápida no Catálogo Siscomex")
    
    if df_siscomex is not None:
        opcoes_situacao = df_siscomex['situacao'].unique().tolist() if 'situacao' in df_siscomex.columns else []
        situacao_selecionada = st.multiselect("Filtrar por Situação do Item:", options=opcoes_situacao, default=opcoes_situacao)
        
        termo_busca = st.text_input("Digite o Código do Siscomex, Código Interno, NCM ou parte da descrição:")
        
        if 'situacao' in df_siscomex.columns:
            df_base_consulta = df_siscomex[df_siscomex['situacao'].isin(situacao_selecionada)]
        else:
            df_base_consulta = df_siscomex.copy()
        
        colunas_exibir_consulta = [c for c in ['codigo', 'codigosInterno', 'ncm', 'descricao', 'situacao'] if c in df_base_consulta.columns]
        
        if termo_busca:
            c1 = df_base_consulta['codigo'].str.contains(termo_busca, case=False, na=False) if 'codigo' in df_base_consulta.columns else False
            c2 = df_base_consulta['codigosInterno'].str.contains(termo_busca, case=False, na=False) if 'codigosInterno' in df_base_consulta.columns else False
            c3 = df_base_consulta['descricao'].str.contains(termo_busca, case=False, na=False) if 'descricao' in df_base_consulta.columns else False
            c4 = df_base_consulta['ncm'].str.contains(termo_busca, case=False, na=False) if 'ncm' in df_base_consulta.columns else False
            
            df_busca = df_base_consulta[c1 | c2 | c3 | c4]
            st.write(f"Resultados encontrados: {len(df_busca)}")
            st.dataframe(df_busca[colunas_exibir_consulta], use_container_width=True)
        else:
            st.write(f"Mostrando os primeiros 20 itens filtrados ({len(df_base_consulta)} no total):")
            st.dataframe(df_base_consulta[colunas_exibir_consulta].head(20), use_container_width=True)
