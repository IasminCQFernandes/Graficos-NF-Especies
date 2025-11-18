import streamlit as st
import pandas as pd
import pyodbc
from datetime import date
import plotly.express as px
from io import BytesIO

# --- Configurações de Conexão com o Banco de Dados (SUAS CONFIGURAÇÕES)
# NOVO Bloco de Configuração de Conexão
DB_CONFIG = {
    "DRIVER": st.secrets["sqlserver"]["DRIVER"], 
    "SERVER": st.secrets["sqlserver"]["SERVER"],
    "DATABASE": st.secrets["sqlserver"]["DATABASE"],
    "UID": st.secrets["sqlserver"]["UID"],
    "PWD": st.secrets["sqlserver"]["PWD"]
}

print(DB_CONFIG)

## ⚙️ Gerenciamento da Conexão
@st.cache_resource 
def get_db_connection():
    # 🚨 Lendo as configurações do banco de dados a partir de st.secrets
    try:
        db_secrets = st.secrets["sqlserver"]
    except KeyError:
        st.error("❌ As configurações do banco de dados (chave 'sqlserver') não foram encontradas nas secrets do Streamlit.")
        return None

    try:
        # Construindo a string de conexão a partir das secrets
        conn_str = (
            f"DRIVER={db_secrets['DRIVER']};SERVER={db_secrets['SERVER']};"
            f"DATABASE={db_secrets['DATABASE']};UID={db_secrets['UID']};PWD={db_secrets['PWD']}"
        )
        
        conn = pyodbc.connect(conn_str, timeout=5)
        return conn
    except pyodbc.Error as e:
        sqlstate = e.args[0]
        st.error(f"❌ Erro de Conexão/SQL ({sqlstate}):")
        st.exception(e) # Adicionado para melhor diagnóstico
        return None
    except Exception as e:
        st.error(f"❌ Erro inesperado ao conectar:")
        st.exception(e)
        return None

## 🔎 Função de Busca de Dados
@st.cache_data
def get_data(_conn, obra, empresa_str, especie, data_inicial, data_final):
    # ... (Função get_data mantida)
    if _conn is None:
        return pd.DataFrame()

    base_query = """
    SELECT 
        NumProc_Pag, Empresa_pag, NumParc_Pag, ObraProc_Pag, CodForn_Pag,
        DataProc_Pag, ValorProc_Pag, NumFiscal_Pag, Serie_nfe, Especie_nfe, Tipo_nfe,
        DataEmis_nfe, DataSaiEnt_nfe, DataCad_nfe 
    FROM 
        ContasPagas
    LEFT JOIN 
        NotasFiscaisEnt ON Empresa_pag = Empresa_nfe
        AND Obra_nfe = ObraProc_Pag
        AND NumFiscal_Pag = NumNfAux_nfe
        AND CodPes_nfe = CodForn_Pag
    """
    
    conditions = []
    params = []

    if obra and obra.strip(): 
        conditions.append("ObraProc_Pag = ?")
        params.append(obra.strip())

    if empresa_str and empresa_str.strip():
        try:
            empresa_id = int(empresa_str.strip())
            conditions.append("Empresa_pag = ?")
            params.append(empresa_id)
        except ValueError:
            st.error(f"⚠️ Valor inválido para Empresa: '{empresa_str}'. Por favor, digite um número inteiro.")
            return pd.DataFrame()
    
    if especie != 'ALL':
        conditions.append("Especie_nfe = ?")
        params.append(especie)

    conditions.append("DataProc_Pag >= ?")
    params.append(data_inicial)
    conditions.append("DataProc_Pag <= ?")
    params.append(data_final)
    
    where_clause = " AND ".join(conditions)
    final_query = f"{base_query} WHERE {where_clause}"

    try:
        df = pd.read_sql(final_query, _conn, params=params) 
        return df
    except pyodbc.Error as e:
        st.error(f"❌ Erro ao executar a consulta:")
        st.exception(e)
        return pd.DataFrame()


## 🛠️ Layout do Aplicativo Streamlit
# ... (Restante do código é o mesmo)
st.set_page_config(layout="wide", page_title="Consulta Contas Pagas")

st.title("🔎 Consulta Espécie NF de Contas Pagas")

conn = get_db_connection()

if conn is None:
    st.warning("Não foi possível conectar ao banco de dados.")
else:
    # --- Widgets de Filtro na Sidebar ---
    with st.sidebar:
        st.header("Opções de Filtro")

        obra_proc_pag = st.text_input("**Obra (ObraProc_Pag):**", value='', placeholder='Deixe vazio para todas as obras')

        empresa_pag_input = st.text_input(
            "**Empresa (ID numérico):**", 
            value='', 
            placeholder='Deixe vazio para todas as empresas'
        )

        especie_options = ['ALL', 'RE', 'NF', 'CT', 'CF', 'OU']
        especie_nfe = st.selectbox(
            "**Espécie (Especie_nfe):**", 
            options=especie_options,
            format_func=lambda x: "Todas as Espécies" if x == 'ALL' else x, 
            index=0
        )

        st.subheader("Período de Pagamento")
        default_start = date(2020, 1, 1)
        default_end = date(2021, 1, 1)
        
        data_proc_pag_min = st.date_input("**Data Inicial (DataProc_Pag >=):**", value=default_start)
        data_proc_pag_max = st.date_input("**Data Final (DataProc_Pag <=):**", value=default_end)

    # --- Execução da Consulta e Exibição ---

    if data_proc_pag_min > data_proc_pag_max:
        st.error("🚨 A data inicial não pode ser maior que a data final.")
    else:
        df_resultado = get_data(
            _conn=conn,
            obra=obra_proc_pag,
            empresa_str=empresa_pag_input, 
            especie=especie_nfe,
            data_inicial=data_proc_pag_min, 
            data_final=data_proc_pag_max
        )

        if not df_resultado.empty:
            
            # Geração do Gráfico de Barras por Espécie
            df_contagem = df_resultado.groupby('Especie_nfe').size().reset_index(name='Contagem')
            
            fig = px.bar(
                df_contagem, 
                x='Especie_nfe', 
                y='Contagem', 
                title='Distribuição de Registros por Espécie',
                labels={'Especie_nfe': 'Espécie de Nota Fiscal', 'Contagem': 'Número de Registros'},
                color='Especie_nfe',
                text='Contagem'
            )
            
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # -----------------------------------------------

            st.subheader(f"Resultados Encontrados: **{len(df_resultado)}** registros")
            st.dataframe(df_resultado, use_container_width=True)
            
            ## 📥 BLOCO PARA DOWNLOAD XLSX
            
            @st.cache_data
            def convert_df_to_xlsx(df):
                """Converte o DataFrame para um arquivo XLSX em memória."""
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='ContasPagas')
                return output.getvalue()
            
            # Prepara os dados para download
            xlsx_data = convert_df_to_xlsx(df_resultado)
            
            # Exibe o botão de download
            st.download_button(
                label="📥 Baixar Dados como XLSX (Excel)",
                data=xlsx_data,
                file_name=f'contas_pagas_{date.today().strftime("%Y%m%d")}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            ## FIM DO BLOCO

        else:
            st.info("ℹ️ Nenhum dado encontrado com os filtros selecionados.")
            
        st.markdown("---")
        st.caption("Filtros Aplicados (Lógica):")
        obra_display = obra_proc_pag if obra_proc_pag.strip() else 'TODAS'
        empresa_display = empresa_pag_input if empresa_pag_input.strip() else 'TODAS'
        especie_display = especie_nfe if especie_nfe != 'ALL' else 'TODAS'
        st.code(f"""
        ObraProc_Pag: {obra_display}
        Empresa_pag: {empresa_display}
        Especie_nfe: {especie_display}
        DataProc_Pag: entre {data_proc_pag_min} e {data_proc_pag_max}
        """)