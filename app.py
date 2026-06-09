import streamlit as st
import pandas as pd
import json

# Configuração da página do aplicativo
st.set_page_config(page_title="GMC - Siscomex & Invoice Auditor", layout="wide")

st.title("📊 GMC - Sistema de Auditoria e Consulta Siscomex")
st.write("Versão 1.1 - Ajustado para linha 14 de cabeçalho")

# -------------------------------------------------------------------------
# BARRA LATERAL: Upload do Banco de Dados
# -------------------------------------------------------------------------
st.sidebar.header("📁 Base de Dados do Siscomex")
arquivo_json = st.sidebar.file_uploader("Suba o JSON atualizado do Siscomex aqui", type=["json"])

# Inicializa a base de dados do Siscomex
df_siscomex = None

if arquivo_json is not None:
    dados = json.load(arquivo_json)
    df_siscomex = pd.json_normalize(dados)
    
    # PADRONIZAÇÃO DOS 10 DÍGITOS: Transforma o código do Siscomex (ex: 1) em '0000000001'
    if 'codigo' in df_siscomex.columns:
        df_siscomex['codigo'] = df_siscomex['codigo'].astype(str).str.strip().str.zfill(10)
        
    # Preserva os zeros à esquerda do NCM e limpa o código interno para o cruzamento
    if 'ncm' in df_siscomex.columns:
        df_siscomex['ncm'] = df_siscomex['ncm'].astype(str).str.strip()
    if 'codigosInterno' in df_siscomex.columns:
        df_siscomex['codigosInterno'] = df_siscomex['codigosInterno'].astype(str).str.strip()
        
    st.sidebar.success("✅ Banco Siscomex carregado com sucesso!")
else:
    st.sidebar.warning("⚠️ Aguardando o arquivo JSON do Siscomex para ativar o sistema.")

# -------------------------------------------------------------------------
# CRIAÇÃO DAS ABAS DE NAVEGAÇÃO
# -------------------------------------------------------------------------
aba_auditoria, aba_consulta = st.tabs(["🔍 Validar Nova Invoice", "📋 Consultar Catálogo"])

# -------------------------------------------------------------------------
# ABA 1: VALIDAR NOVA INVOICE
# -------------------------------------------------------------------------
with aba_auditoria:
    st.header("Análise de Commercial Invoice")
    st.write("Arrastando a sua Invoice aqui, o sistema pulará o cabeçalho e fará o cruzamento.")
    
    arquivo_invoice = st.file_uploader("Suba o arquivo Excel da Invoice", type=["xlsx", "xls"])
    
    if arquivo_invoice is not None and df_siscomex is not None:
        # CORREÇÃO: skiprows=13 pula as 13 primeiras linhas. A linha 14 vira o cabeçalho (ITEM, COD, NCM) e os dados iniciam na 15.
        df_invoice = pd.read_excel(arquivo_invoice, skiprows=13, dtype={'COD': str, 'NCM': str})
        
        # Limpa espaços invisíveis que o exportador possa ter digitado sem querer
        df_invoice['COD'] = df_invoice['COD'].astype(str).str.strip()
        df_invoice['NCM'] = df_invoice['NCM'].astype(str).str.strip()
        
        # CRUZAMENTO DOS DADOS (O 'Mesclar' do Power Query no Python)
        df_resultado = pd.merge(
            df_invoice, 
            df_siscomex[['codigosInterno', 'codigo', 'ncm', 'descricao', 'situacao']], 
            left_on='COD', 
            right_on='codigosInterno', 
            how='left',
            suffixes=('_invoice', '_siscomex')
        )
        
        # Regras de Negócio para definição do Status
        def definir_status(row):
            if pd.isna(row['codigosInterno']) or row['codigosInterno'] == 'nan':
                return "🚨 Cadastrar no Siscomex"
            elif row['NCM'] != row['ncm']:
                return "⚠️ Divergência de NCM"
            else:
                return "✅ Tudo Certo"
                
        df_resultado['Status Auditoria'] = df_resultado.apply(definir_status, axis=1)
        
        # Reorganiza as colunas para o resultado ficar visualmente perfeito
        colunas_exibicao = [
            'ITEM', 'COD', 'NCM', 'PRODUCT DESCRIPTION', 'QTY', 
            'codigo', 'ncm', 'Status Auditoria'
        ]
        # Mantém apenas as colunas que realmente existem para evitar erros de layout
        colunas_exibicao = [c for c in colunas_exibicao if c in df_resultado.columns]
        
        # Filtros rápidos na tela
        status_selecionado = st.multiselect(
            "Filtrar por Status de Auditoria:",
            options=df_resultado['Status Auditoria'].unique(),
            default=df_resultado['Status Auditoria'].unique()
        )
        
        df_filtrado = df_resultado[df_resultado['Status Auditoria'].isin(status_selecionado)]
        
        # Exibe a tabela de auditoria na tela
        st.dataframe(df_filtrado[colunas_exibicao], use_container_width=True)
        
    elif df_siscomex is None:
        st.info("Por favor, suba a base do Siscomex na barra lateral primeiro.")

# -------------------------------------------------------------------------
# ABA 2: INTERFACE DE CONSULTA (O SEU GOOGLE DO SISCOMEX)
# -------------------------------------------------------------------------
with aba_consulta:
    st.header("Busca Rápida no Catálogo Siscomex")
    
    if df_siscomex is not None:
        termo_busca = st.text_input("Digite o Código do Siscomex, Código Interno, NCM ou parte da descrição:")
        
        if termo_busca:
            # CORREÇÃO: Filtro de busca corrigido e simplificado para evitar erros de sintaxe
            df_busca = df_siscomex[
                df_siscomex['codigo'].str.contains(termo_busca, case=False, na=False) |
                df_siscomex['codigosInterno'].str.contains(termo_busca, case=False, na=False) |
                df_siscomex['descricao'].str.contains(termo_busca, case=False, na=False) |
                df_siscomex['ncm'].str.contains(termo_busca, case=False, na=False)
            ]
            st.write(f"Resultados encontrados: {len(df_busca)}")
            st.dataframe(df_busca[['codigo', 'codigosInterno', 'ncm', 'descricao', 'situacao']], use_container_width=True)
        else:
            st.write("Mostrando os primeiros 20 itens do seu catálogo (Comece a digitar acima para filtrar):")
            st.dataframe(df_siscomex[['codigo', 'codigosInterno', 'ncm', 'descricao', 'situacao']].head(20), use_container_width=True)
            
    else:
        st.info("Por favor, suba a base do Siscomex na barra lateral para habilitar a consulta.")
