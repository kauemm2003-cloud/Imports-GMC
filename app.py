import streamlit as st
import pandas as pd
import json
import os
import re

# Configuração da página do aplicativo
st.set_page_config(page_title="GMC - Siscomex & Invoice Auditor", layout="wide")

st.title("📊 GMC - Sistema de Auditoria e Consulta Siscomex")
st.write("Versão 2.2 - Filtros Corrigidos com Sucesso")

NOME_ARQUIVO_BANCO = "banco_siscomex.json"
df_siscomex = None

# FUNÇÃO AUXILIAR: Formata o NCM (ex: 85363090) para o padrão com pontos (8536.30.90)
def formatar_ncm(ncm_sujo):
    ncm_limpo = re.sub(r'\D', '', str(ncm_sujo)) # Remove qualquer coisa que não seja número
    if len(ncm_limpo) == 8:
        return f"{ncm_limpo[:4]}.{ncm_limpo[4:6]}.{ncm_limpo[6:]}"
    return ncm_sujo

# FUNÇÃO AUXILIAR: Limpa colchetes, aspas e espaços de dentro dos códigos do JSON
def limpar_codigo_json(codigo_sujo):
    if pd.isna(codigo_sujo):
        return ""
    texto = str(codigo_sujo)
    texto_limpo = re.sub(r"[\[\]'\" ]", "", texto)
    return texto_limpo

# CARREGAMENTO DO BANCO DE DADOS FIXO
if os.path.exists(NOME_ARQUIVO_BANCO):
    try:
        with open(NOME_ARQUIPO_BANCO if 'NOME_ARQUIPO_BANCO' in locals() else NOME_ARQUIVO_BANCO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        df_siscomex = pd.json_normalize(dados)
        
        # APLICANDO AS CORREÇÕES CRÍTICAS NA BASE DO SISCOMEX
        if 'codigosInterno' in df_siscomex.columns:
            df_siscomex['codigosInterno'] = df_siscomex['codigosInterno'].apply(limpar_codigo_json)
        if 'codigo' in df_siscomex.columns:
            df_siscomex['codigo'] = df_siscomex['codigo'].apply(limpar_codigo_json).str.zfill(10)
        if 'ncm' in df_siscomex.columns:
            df_siscomex['ncm'] = df_siscomex['ncm'].apply(formatar_ncm)
            
        st.sidebar.success("✅ Banco Siscomex carregado automaticamente da nuvem!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler o banco de dados: {e}")
else:
    st.sidebar.warning(f"⚠️ Arquivo '{NOME_ARQUIVO_BANCO}' não encontrado no GitHub. Suba o JSON no seu repositório.")

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
        
        def definir_status(row):
            if pd.isna(row['codigosInterno']) or str(row['codigosInterno']).strip() == "" or str(row['codigosInterno']) == 'nan':
                return "🚨 Cadastrar no Siscomex"
            elif row['NCM'] != row['ncm']:
                return "⚠️ Divergência de NCM"
            else:
                return "✅ Tudo Certo"
                
        df_resultado['Status Auditoria'] = df_resultado.apply(definir_status, axis=1)
        
        colunas_exibicao = [
            'ITEM', 'COD', 'NCM', 'PRODUCT DESCRIPTION', 'QTY', 
            'codigo', 'ncm', 'Status Auditoria'
        ]
        colunas_exibicao = [c for c in colunas_exibicao if c in df_resultado.columns]
        
        status_selecionado = st.multiselect(
            "Filtrar por Status de Auditoria:",
            options=df_resultado['Status Auditoria'].unique(),
            default=df_resultado['Status Auditoria'].unique()
        )
        
        df_filtrado = df_resultado[df_resultado['Status Auditoria'].isin(status_selecionado)]
        st.dataframe(df_filtrado[colunas_exibicao], use_container_width=True)
        
    elif df_siscomex is None:
        st.info("Aguardando o arquivo de banco de dados no GitHub para habilitar a auditoria.")

# -------------------------------------------------------------------------
# ABA 2: INTERFACE DE CONSULTA (O SEU GOOGLE DO SISCOMEX)
# -------------------------------------------------------------------------
with aba_consulta:
    st.header("Busca Rápida no Catálogo Siscomex")
    
    if df_siscomex is not None:
        opcoes_situacao = df_siscomex['situacao'].unique().tolist() if 'situacao' in df_siscomex.columns else []
        situacao_selecionada = st.multiselect("Filtrar por Situação do Item:", options=opcoes_situacao, default=opcoes_situacao)
        
        termo_busca = st.text_input("Digite o Código do Siscomex, Código Interno, NCM ou parte da descrição:")
        
        # Filtra por situação primeiro se a coluna existir
        if 'situacao' in df_siscomex.columns:
            df_base_consulta = df_siscomex[df_siscomex['situacao'].isin(situacao_selecionada)]
        else:
            df_base_consulta = df_siscomex.copy()
        
        colunas_exibir_consulta = [c for c in ['codigo', 'codigosInterno', 'ncm', 'descricao', 'situacao'] if c in df_base_consulta.columns]
        
        if termo_busca:
            # Condições limpas, isoladas por parênteses e sem linhas duplicadas
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
