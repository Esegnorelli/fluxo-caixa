import sqlite3
from datetime import date, datetime, timedelta
from io import StringIO, BytesIO
from typing import Optional, Dict, List, Tuple
import calendar

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------- Config & Estilo --------------------
st.set_page_config(
    page_title="Fluxo de Caixa Pro", 
    page_icon="💸", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
<style>
:root { 
    --top-pad: 1.5rem; 
    --primary-color: #1f77b4;
    --success-color: #2ca02c;
    --warning-color: #ff7f0e;
    --error-color: #d62728;
}
.block-container {padding-top: var(--top-pad);}
[data-testid="stMetricValue"] {font-weight: 700; font-size: 1.5rem;}
[data-testid="stMetricDelta"] {font-size: 1rem;}
div[data-testid="stDataFrame"] div[role="grid"] {font-size: 0.9rem;}
h1, h2, h3 { margin-top: 0.5rem; margin-bottom: 0.8rem; }
.metric-card {
    background: white;
    padding: 1rem;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    border-left: 4px solid var(--primary-color);
}
.positive { color: var(--success-color) !important; }
.negative { color: var(--error-color) !important; }
.stTabs [data-baseweb="tab-list"] {gap: 2rem;}
.stSelectbox > div > div { background-color: #f8f9fa; }
</style>
""",
    unsafe_allow_html=True,
)

# -------------------- Constantes --------------------
DB_PATH = "fluxo_pro.db"
LANC_COLUMNS = ["id", "data", "empresa", "descricao", "categoria", "tipo", "valor", "observacoes", "created_at", "updated_at"]
TIPOS = ["Entrada", "Saída"]
CATEGORIAS_ENTRADA = [
    "Vendas", "Serviços", "Juros Recebidos", "Aluguéis Recebidos", 
    "Dividendos", "Outras Receitas", "Transferência Entre Contas"
]
CATEGORIAS_SAIDA = [
    "Fornecedores", "Salários", "Impostos", "Aluguel", "Utilities", 
    "Marketing", "Manutenção", "Combustível", "Alimentação", 
    "Outras Despesas", "Transferência Entre Contas"
]
EMPRESAS_PADRAO = [
    "Gestão", "Gestão Fundo de Propaganda", "Effexus", 
    "Effexus - utilizado para gestão", "Indústria", "Adriana"
]
# -------------------- Classes de Dados --------------------
class LancamentoManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa o banco de dados com as tabelas necessárias."""
        conn = self.get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                empresa TEXT NOT NULL,
                descricao TEXT,
                categoria TEXT,
                tipo TEXT NOT NULL,
                valor REAL NOT NULL,
                observacoes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa TEXT NOT NULL,
                mes TEXT NOT NULL,
                meta_entrada REAL DEFAULT 0,
                meta_saida REAL DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lanc_data ON lancamentos(data)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lanc_empresa ON lancamentos(empresa)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lanc_tipo ON lancamentos(tipo)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metas_empresa_mes ON metas(empresa, mes)")
        conn.close()
    
    def get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def insert_lancamento(self, dados: Dict) -> bool:
        try:
            conn = self.get_conn()
            now = datetime.now().isoformat(timespec="seconds")
            
            conn.execute("""
                INSERT INTO lancamentos 
                (data, empresa, descricao, categoria, tipo, valor, observacoes, created_at, updated_at) 
                VALUES (?,?,?,?,?,?,?,?,?)
            """, [
                dados.get("data"),
                dados.get("empresa"),
                dados.get("descricao", ""),
                dados.get("categoria", ""),
                dados.get("tipo", "Entrada"),
                float(dados.get("valor", 0)),
                dados.get("observacoes", ""),
                now, now
            ])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao inserir lançamento: {e}")
            return False
    
    def read_lancamentos(self, filtros: Optional[Dict] = None) -> pd.DataFrame:
        conn = self.get_conn()
        
        query = "SELECT * FROM lancamentos"
        params = []
        
        if filtros:
            conditions = []
            if filtros.get("empresa"):
                conditions.append("empresa = ?")
                params.append(filtros["empresa"])
            if filtros.get("data_inicio"):
                conditions.append("data >= ?")
                params.append(filtros["data_inicio"])
            if filtros.get("data_fim"):
                conditions.append("data <= ?")
                params.append(filtros["data_fim"])
            if filtros.get("tipo"):
                conditions.append("tipo = ?")
                params.append(filtros["tipo"])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY data DESC, id DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame(columns=LANC_COLUMNS)
        
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        return df
    
    def update_lancamento(self, id_: int, dados: Dict) -> bool:
        try:
            conn = self.get_conn()
            now = datetime.now().isoformat(timespec="seconds")
            
            conn.execute("""
                UPDATE lancamentos 
                SET data=?, empresa=?, descricao=?, categoria=?, tipo=?, valor=?, observacoes=?, updated_at=? 
                WHERE id=?
            """, [
                dados.get("data"),
                dados.get("empresa"),
                dados.get("descricao", ""),
                dados.get("categoria", ""),
                dados.get("tipo", "Entrada"),
                float(dados.get("valor", 0)),
                dados.get("observacoes", ""),
                now, int(id_)
            ])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar lançamento: {e}")
            return False
    
    def delete_lancamento(self, id_: int) -> bool:
        try:
            conn = self.get_conn()
            conn.execute("DELETE FROM lancamentos WHERE id = ?", [int(id_)])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao excluir lançamento: {e}")
            return False

class AnalyticsEngine:
    def __init__(self, manager: LancamentoManager):
        self.manager = manager
    
    def calcular_kpis(self, df: pd.DataFrame) -> Dict:
        """Calcula KPIs principais."""
        if df.empty:
            return {"entradas": 0, "saidas": 0, "saldo": 0, "total_lancamentos": 0}
        
        df_clean = df.copy()
        df_clean["tipo_norm"] = df_clean["tipo"].astype(str).str.strip().str.lower()
        
        entradas = df_clean.loc[df_clean["tipo_norm"] == "entrada", "valor"].sum()
        saidas = df_clean.loc[df_clean["tipo_norm"] == "saída", "valor"].sum()
        saldo = entradas - saidas
        total_lancamentos = len(df_clean)
        
        return {
            "entradas": float(entradas),
            "saidas": float(saidas),
            "saldo": float(saldo),
            "total_lancamentos": total_lancamentos
        }
    
    def calcular_trends(self, df: pd.DataFrame, periodo: int = 6) -> Dict:
        """Calcula tendências dos últimos N meses."""
        if df.empty:
            return {"trend_entradas": 0, "trend_saidas": 0, "trend_saldo": 0}
        
        df_trend = df.copy()
        df_trend["data_dt"] = pd.to_datetime(df_trend["data"], errors="coerce")
        df_trend = df_trend.dropna(subset=["data_dt"])
        
        # Últimos N meses
        data_corte = datetime.now() - timedelta(days=periodo * 30)
        df_trend = df_trend[df_trend["data_dt"] >= data_corte]
        
        if df_trend.empty:
            return {"trend_entradas": 0, "trend_saidas": 0, "trend_saldo": 0}
        
        df_trend["mes"] = df_trend["data_dt"].dt.to_period("M")
        df_trend["tipo_norm"] = df_trend["tipo"].astype(str).str.strip().str.lower()
        
        monthly = df_trend.groupby(["mes", "tipo_norm"])["valor"].sum().unstack(fill_value=0)
        
        if "entrada" in monthly.columns and len(monthly) >= 2:
            trend_entradas = monthly["entrada"].pct_change().mean() * 100
        else:
            trend_entradas = 0
        
        if "saída" in monthly.columns and len(monthly) >= 2:
            trend_saidas = monthly["saída"].pct_change().mean() * 100
        else:
            trend_saidas = 0
        
        saldo_mensal = monthly.get("entrada", 0) - monthly.get("saída", 0)
        if len(saldo_mensal) >= 2:
            trend_saldo = saldo_mensal.pct_change().mean() * 100
        else:
            trend_saldo = 0
        
        return {
            "trend_entradas": float(trend_entradas),
            "trend_saidas": float(trend_saidas),
            "trend_saldo": float(trend_saldo)
        }
import sqlite3
from datetime import date, datetime, timedelta
from io import StringIO, BytesIO
from typing import Optional, Dict, List, Tuple
import calendar

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------- Config & Estilo --------------------
st.set_page_config(
    page_title="Fluxo de Caixa Pro", 
    page_icon="💸", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
<style>
:root { 
    --top-pad: 1.5rem; 
    --primary-color: #1f77b4;
    --success-color: #2ca02c;
    --warning-color: #ff7f0e;
    --error-color: #d62728;
}
.block-container {padding-top: var(--top-pad);} 
[data-testid="stMetricValue"] {font-weight: 700; font-size: 1.5rem;}
[data-testid="stMetricDelta"] {font-size: 1rem;}
div[data-testid="stDataFrame"] div[role="grid"] {font-size: 0.9rem;}
h1, h2, h3 { margin-top: 0.5rem; margin-bottom: 0.8rem; }
.metric-card {
    background: white;
    padding: 1rem;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    border-left: 4px solid var(--primary-color);
}
.positive { color: var(--success-color) !important; }
.negative { color: var(--error-color) !important; }
.stTabs [data-baseweb="tab-list"] {gap: 2rem;}
.stSelectbox > div > div { background-color: #f8f9fa; }
</style>
""",
    unsafe_allow_html=True,
)

# -------------------- Constantes --------------------
DB_PATH = "fluxo_pro.db"
LANC_COLUMNS = ["id", "data", "empresa", "descricao", "categoria", "tipo", "valor", "observacoes", "created_at", "updated_at"]
TIPOS = ["Entrada", "Saída"]
CATEGORIAS_ENTRADA = [
    "Vendas", "Serviços", "Juros Recebidos", "Aluguéis Recebidos", 
    "Dividendos", "Outras Receitas", "Transferência Entre Contas"
]
CATEGORIAS_SAIDA = [
    "Fornecedores", "Salários", "Impostos", "Aluguel", "Utilities", 
    "Marketing", "Manutenção", "Combustível", "Alimentação", 
    "Outras Despesas", "Transferência Entre Contas"
]
EMPRESAS_PADRAO = [
    "Gestão", "Gestão Fundo de Propaganda", "Effexus", 
    "Effexus - utilizado para gestão", "Indústria", "Adriana"
]

# -------------------- Classes de Dados --------------------
class LancamentoManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa o banco de dados com as tabelas necessárias."""
        conn = self.get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                empresa TEXT NOT NULL,
                descricao TEXT,
                categoria TEXT,
                tipo TEXT NOT NULL,
                valor REAL NOT NULL,
                observacoes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa TEXT NOT NULL,
                mes TEXT NOT NULL,
                meta_entrada REAL DEFAULT 0,
                meta_saida REAL DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lanc_data ON lancamentos(data)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lanc_empresa ON lancamentos(empresa)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lanc_tipo ON lancamentos(tipo)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metas_empresa_mes ON metas(empresa, mes)")
        conn.close()
    
    def get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def insert_lancamento(self, dados: Dict) -> bool:
        """Insere um novo lançamento."""
        try:
            now = datetime.now().isoformat(timespec="seconds")
            conn = self.get_conn()
            conn.execute("""
                INSERT INTO lancamentos 
                (data, empresa, descricao, categoria, tipo, valor, observacoes, created_at, updated_at) 
                VALUES (?,?,?,?,?,?,?,?,?)
            """, [
                dados.get("data"),
                dados.get("empresa"),
                dados.get("descricao", ""),
                dados.get("categoria", ""),
                dados.get("tipo", "Entrada"),
                float(dados.get("valor", 0)),
                dados.get("observacoes", ""),
                now, now
            ])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao inserir lançamento: {e}")
            return False
    
    def read_lancamentos(self, filtros: Optional[Dict] = None) -> pd.DataFrame:
        """Lê lançamentos com filtros opcionais."""
        conn = self.get_conn()
        query = "SELECT * FROM lancamentos"
        params: List = []
        if filtros:
            conditions: List[str] = []
            if filtros.get("empresa"):
                conditions.append("empresa = ?")
                params.append(filtros["empresa"])
            if filtros.get("data_inicio"):
                conditions.append("data >= ?")
                params.append(filtros["data_inicio"])
            if filtros.get("data_fim"):
                conditions.append("data <= ?")
                params.append(filtros["data_fim"])
            if filtros.get("tipo"):
                conditions.append("tipo = ?")
                params.append(filtros["tipo"])
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY data DESC, id DESC"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        if df.empty:
            return pd.DataFrame(columns=LANC_COLUMNS)
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        return df
    
    def update_lancamento(self, id_: int, dados: Dict) -> bool:
        """Atualiza um lançamento existente."""
        try:
            now = datetime.now().isoformat(timespec="seconds")
            conn = self.get_conn()
            conn.execute("""
                UPDATE lancamentos 
                SET data=?, empresa=?, descricao=?, categoria=?, tipo=?, valor=?, observacoes=?, updated_at=? 
                WHERE id=?
            """, [
                dados.get("data"),
                dados.get("empresa"),
                dados.get("descricao", ""),
                dados.get("categoria", ""),
                dados.get("tipo", "Entrada"),
                float(dados.get("valor", 0)),
                dados.get("observacoes", ""),
                now, int(id_)
            ])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar lançamento: {e}")
            return False
    
    def delete_lancamento(self, id_: int) -> bool:
        """Exclui um lançamento."""
        try:
            conn = self.get_conn()
            conn.execute("DELETE FROM lancamentos WHERE id = ?", [int(id_)])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao excluir lançamento: {e}")
            return False

class AnalyticsEngine:
    def __init__(self, manager: LancamentoManager):
        self.manager = manager
    
    def calcular_kpis(self, df: pd.DataFrame) -> Dict:
        """Calcula KPIs principais."""
        if df.empty:
            return {"entradas": 0, "saidas": 0, "saldo": 0, "total_lancamentos": 0}
        df_clean = df.copy()
        df_clean["tipo_norm"] = df_clean["tipo"].astype(str).str.strip().str.lower()
        entradas = df_clean.loc[df_clean["tipo_norm"] == "entrada", "valor"].sum()
        saidas = df_clean.loc[df_clean["tipo_norm"] == "saída", "valor"].sum()
        saldo = entradas - saidas
        total_lancamentos = len(df_clean)
        return {
            "entradas": float(entradas),
            "saidas": float(saidas),
            "saldo": float(saldo),
            "total_lancamentos": total_lancamentos
        }
    
    def calcular_trends(self, df: pd.DataFrame, periodo: int = 6) -> Dict:
        """Calcula tendências dos últimos N meses."""
        if df.empty:
            return {"trend_entradas": 0, "trend_saidas": 0, "trend_saldo": 0}
        df_trend = df.copy()
        df_trend["data_dt"] = pd.to_datetime(df_trend["data"], errors="coerce")
        df_trend = df_trend.dropna(subset=["data_dt"])
        data_corte = datetime.now() - timedelta(days=periodo * 30)
        df_trend = df_trend[df_trend["data_dt"] >= data_corte]
        if df_trend.empty:
            return {"trend_entradas": 0, "trend_saidas": 0, "trend_saldo": 0}
        df_trend["mes"] = df_trend["data_dt"].dt.to_period("M")
        df_trend["tipo_norm"] = df_trend["tipo"].astype(str).str.strip().str.lower()
        monthly = df_trend.groupby(["mes", "tipo_norm"])["valor"].sum().unstack(fill_value=0)
        if "entrada" in monthly.columns and len(monthly) >= 2:
            trend_entradas = monthly["entrada"].pct_change().mean() * 100
        else:
            trend_entradas = 0
        if "saída" in monthly.columns and len(monthly) >= 2:
            trend_saidas = monthly["saída"].pct_change().mean() * 100
        else:
            trend_saidas = 0
        saldo_mensal = monthly.get("entrada", 0) - monthly.get("saída", 0)
        if len(saldo_mensal) >= 2:
            trend_saldo = saldo_mensal.pct_change().mean() * 100
        else:
            trend_saldo = 0
        return {
            "trend_entradas": float(trend_entradas),
            "trend_saidas": float(trend_saidas),
            "trend_saldo": float(trend_saldo)
        }

# -------------------- Utilitários --------------------
def fmt_currency(value: float, simbolo: str = "R$") -> str:
    try:
        valor = float(value)
        formatted = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        prefix = f"{simbolo} " if valor >= 0 else f"-{simbolo} "
        return f"{prefix}{formatted}"
    except Exception:
        return f"{simbolo} 0,00"

def fmt_percentage(value: float) -> str:
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"

def get_empresas_list(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return EMPRESAS_PADRAO
    empresas = sorted([e for e in df["empresa"].dropna().unique() if e.strip()])
    return empresas or EMPRESAS_PADRAO

def criar_grafico_linha_tempo(df: pd.DataFrame, titulo: str) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    df_plot = df.copy()
    df_plot["data_dt"] = pd.to_datetime(df_plot["data"], errors="coerce")
    df_plot = df_plot.dropna(subset=["data_dt"])
    df_plot["mes"] = df_plot["data_dt"].dt.to_period("M").astype(str)
    df_plot["tipo_norm"] = df_plot["tipo"].astype(str).str.strip().str.lower()
    monthly = df_plot.groupby(["mes", "tipo_norm"])["valor"].sum().unstack(fill_value=0)
    monthly = monthly.reset_index()
    monthly["data_mes"] = pd.to_datetime(monthly["mes"] + "-01")
    if "entrada" in monthly.columns:
        fig.add_trace(
            go.Scatter(
                x=monthly["data_mes"],
                y=monthly["entrada"],
                name="Entradas",
                line=dict(color="#2ca02c", width=3),
                mode="lines+markers"
            )
        )
    if "saída" in monthly.columns:
        fig.add_trace(
            go.Scatter(
                x=monthly["data_mes"],
                y=monthly["saída"],
                name="Saídas",
                line=dict(color="#d62728", width=3),
                mode="lines+markers"
            )
        )
    if "entrada" in monthly.columns and "saída" in monthly.columns:
        saldo = monthly["entrada"] - monthly["saída"]
        fig.add_trace(
            go.Scatter(
                x=monthly["data_mes"],
                y=saldo,
                name="Saldo",
                line=dict(color="#1f77b4", width=2, dash="dash"),
                mode="lines+markers"
            ),
            secondary_y=True
        )
    fig.update_layout(
        title=titulo,
        xaxis_title="Período",
        height=500,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="Valor (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Saldo (R$)", secondary_y=True)
    # corrigindo update_xaxis -> update_xaxes
    fig.update_xaxes(type="date")
    return fig

# -------------------- Páginas --------------------
def page_lancamentos():
    st.subheader("📥 Gestão de Lançamentos")
    manager = LancamentoManager(DB_PATH)
    with st.form("novo_lancamento", clear_on_submit=True):
        st.markdown("**➕ Novo Lançamento**")
        col1, col2, col3 = st.columns(3)
        with col1:
            empresas = get_empresas_list(manager.read_lancamentos())
            empresa = st.selectbox("Empresa", empresas)
            data_mov = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        with col2:
            tipo = st.selectbox("Tipo", TIPOS)
            categorias = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_SAIDA
            categoria = st.selectbox("Categoria", categorias)
        with col3:
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        descricao = st.text_input("Descrição")
        observacoes = st.text_area("Observações (opcional)", height=100)
        submitted = st.form_submit_button("💾 Adicionar Lançamento", use_container_width=True)
        if submitted:
            dados = {
                "data": data_mov.isoformat(),
                "empresa": empresa,
                "descricao": descricao,
                "categoria": categoria,
                "tipo": tipo,
                "valor": valor,
                "observacoes": observacoes
            }
            if manager.insert_lancamento(dados):
                st.success("✅ Lançamento adicionado com sucesso!")
                st.rerun()
            else:
                st.error("❌ Erro ao adicionar lançamento")
    st.divider()
    st.markdown("**🔍 Filtros**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        empresas_filtro = ["Todas"] + get_empresas_list(manager.read_lancamentos())
        empresa_filtro = st.selectbox("Filtrar por Empresa", empresas_filtro)
    with col2:
        data_inicio = st.date_input("Data Início", format="DD/MM/YYYY")
    with col3:
        data_fim = st.date_input("Data Fim", format="DD/MM/YYYY")
    with col4:
        tipos_filtro = ["Todos", "Entrada", "Saída"]
        tipo_filtro = st.selectbox("Filtrar por Tipo", tipos_filtro)
    filtros: Dict[str, str] = {}
    if empresa_filtro != "Todas":
        filtros["empresa"] = empresa_filtro
    if data_inicio:
        filtros["data_inicio"] = data_inicio.isoformat()
    if data_fim:
        filtros["data_fim"] = data_fim.isoformat()
    if tipo_filtro != "Todos":
        filtros["tipo"] = tipo_filtro
    df = manager.read_lancamentos(filtros)
    if not df.empty:
        df_display = df.copy()
        df_display["data_dt"] = pd.to_datetime(df_display["data"], errors="coerce")
        df_display["Data"] = df_display["data_dt"].dt.strftime("%d/%m/%Y")
        df_display["Valor"] = df_display["valor"].apply(fmt_currency)
        cols_display = ["id", "Data", "empresa", "descricao", "categoria", "tipo", "Valor"]
        st.markdown(f"**📋 Lançamentos ({len(df)} registros)**")
        st.dataframe(
            df_display[cols_display], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "Data": st.column_config.TextColumn("Data", width="small"),
                "empresa": st.column_config.TextColumn("Empresa", width="medium"),
                "descricao": st.column_config.TextColumn("Descrição", width="large"),
                "categoria": st.column_config.TextColumn("Categoria", width="medium"),
                "tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Valor": st.column_config.TextColumn("Valor", width="small")
            }
        )
    else:
        st.info("📝 Nenhum lançamento encontrado com os filtros aplicados")
    if not df.empty:
        with st.expander("✏️ Editar/Excluir Lançamentos"):
            lancamento_id = st.selectbox("Selecionar Lançamento", df["id"].tolist())
            lancamento = df[df["id"] == lancamento_id].iloc[0]
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**👋 Editar Lançamento**")
                with st.form(f"edit_{lancamento_id}"):
                    empresas_edit = get_empresas_list(df)
                    empresa_edit = st.selectbox("Empresa", empresas_edit, index=empresas_edit.index(lancamento["empresa"]) if lancamento["empresa"] in empresas_edit else 0)
                    data_edit = st.date_input("Data", value=pd.to_datetime(lancamento["data"]).date(), format="DD/MM/YYYY")
                    tipo_edit = st.selectbox("Tipo", TIPOS, index=TIPOS.index(lancamento["tipo"]) if lancamento["tipo"] in TIPOS else 0)
                    categorias_edit = CATEGORIAS_ENTRADA if tipo_edit == "Entrada" else CATEGORIAS_SAIDA
                    categoria_idx = categorias_edit.index(lancamento["categoria"]) if lancamento["categoria"] in categorias_edit else 0
                    categoria_edit = st.selectbox("Categoria", categorias_edit, index=categoria_idx)
                    valor_edit = st.number_input("Valor (R$)", value=float(lancamento["valor"]), step=0.01, format="%.2f")
                    descricao_edit = st.text_input("Descrição", value=lancamento["descricao"] or "")
                    observacoes_edit = st.text_area("Observações", value=lancamento["observacoes"] or "")
                    if st.form_submit_button("💾 Salvar Alterações"):
                        dados_edit = {
                            "data": data_edit.isoformat(),
                            "empresa": empresa_edit,
                            "descricao": descricao_edit,
                            "categoria": categoria_edit,
                            "tipo": tipo_edit,
                            "valor": valor_edit,
                            "observacoes": observacoes_edit
                        }
                        if manager.update_lancamento(lancamento_id, dados_edit):
                            st.success("✅ Lançamento atualizado!")
                            st.rerun()
            with col2:
                st.markdown("**🗑️ Excluir Lançamento**")
                st.write(f"**ID:** {lancamento['id']}")
                st.write(f"**Data:** {pd.to_datetime(lancamento['data']).strftime('%d/%m/%Y')}")
                st.write(f"**Empresa:** {lancamento['empresa']}")
                st.write(f"**Descrição:** {lancamento['descricao']}")
                st.write(f"**Valor:** {fmt_currency(lancamento['valor'])}")
                if st.button("🗑️ Confirmar Exclusão", key=f"delete_{lancamento_id}"):
                    if manager.delete_lancamento(lancamento_id):
                        st.success("✅ Lançamento excluído!")
                        st.rerun()

def page_dashboard():
    st.subheader("📈 Dashboard Executivo")
    manager = LancamentoManager(DB_PATH)
    analytics = AnalyticsEngine(manager)
    col1, col2, col3 = st.columns(3)
    with col1:
        empresas = ["Todas"] + get_empresas_list(manager.read_lancamentos())
        empresa_dash = st.selectbox("Empresa", empresas)
    with col2:
        anos_disponiveis = list(range(2020, datetime.now().year + 2))
        ano_dash = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(datetime.now().year))
    with col3:
        periodo_trend = st.selectbox("Período Tendência", [3, 6, 12], index=1, format_func=lambda x: f"{x} meses")
    filtros: Dict[str, str] = {
        "data_inicio": f"{ano_dash}-01-01",
        "data_fim": f"{ano_dash}-12-31"
    }
    if empresa_dash != "Todas":
        filtros["empresa"] = empresa_dash
    df_filtered = manager.read_lancamentos(filtros)
    kpis = analytics.calcular_kpis(df_filtered)
    trends = analytics.calcular_trends(df_filtered, periodo_trend)
    st.markdown("### 📈 Indicadores Principais")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "💰 Total Entradas",
            fmt_currency(kpis["entradas"]),
            f"{fmt_percentage(trends['trend_entradas'])} ({periodo_trend}m)"
        )
    with col2:
        st.metric(
            "💸 Total Saídas", 
            fmt_currency(kpis["saidas"]),
            f"{fmt_percentage(trends['trend_saidas'])} ({periodo_trend}m)"
        )
    with col3:
        st.metric(
            "💶 Saldo Líquido",
            fmt_currency(kpis["saldo"]),
            f"{fmt_percentage(trends['trend_saldo'])} ({periodo_trend}m)"
        )
    with col4:
        st.metric(
            "📊 Total Lançamentos",
            f"{kpis['total_lancamentos']:,}".replace(",", "."),
            ""
        )
    if df_filtered.empty:
        st.info("📝 Nenhum dado disponível para o período selecionado")
        return
    st.markdown("### 📈 Análise Temporal")
    tab1, tab2, tab3 = st.tabs(["📈 Visão Geral", "🏢 Por Categoria", "📅 Detalhamento Mensal"])
    with tab1:
        fig_principal = criar_grafico_linha_tempo(df_filtered, f"Evolução Financeira - {ano_dash}")
        st.plotly_chart(fig_principal, use_container_width=True)
        col_a, col_b = st.columns(2)
        with col_a:
            fig_pie_tipo = px.pie(
                values=[kpis["entradas"], kpis["saidas"]],
                names=["Entradas", "Saídas"],
                title="Distribuição: Entradas vs Saídas",
                color_discrete_map={"Entradas": "#2ca02c", "Saídas": "#d62728"}
            )
            st.plotly_chart(fig_pie_tipo, use_container_width=True)
        with col_b:
            if empresa_dash == "Todas":
                df_empresas = df_filtered.groupby("empresa")["valor"].sum().sort_values(ascending=False).head(10)
                fig_bar_empresas = px.bar(
                    x=df_empresas.values,
                    y=df_empresas.index,
                    orientation="h",
                    title="Top 10 Empresas por Movimentação",
                    labels={"x": "Valor Total (R$)", "y": "Empresa"}
                )
                st.plotly_chart(fig_bar_empresas, use_container_width=True)
    with tab2:
        df_cat = df_filtered.groupby(["categoria", "tipo"])["valor"].sum().reset_index()
        if not df_cat.empty:
            fig_cat = px.bar(
                df_cat,
                x="categoria",
                y="valor",
                color="tipo",
                title="Movimentação por Categoria",
                labels={"valor": "Valor (R$)", "categoria": "Categoria"},
                color_discrete_map={"Entrada": "#2ca02c", "Saída": "#d62728"}
            )
            fig_cat.update_xaxes(tickangle=45)
            st.plotly_chart(fig_cat, use_container_width=True)
        st.markdown("**📋 Resumo por Categoria**")
        pivot_cat = df_filtered.pivot_table(
            index="categoria",
            columns="tipo",
            values="valor",
            aggfunc="sum",
            fill_value=0
        ).reset_index()
        if "Entrada" in pivot_cat.columns and "Saída" in pivot_cat.columns:
            pivot_cat["Saldo"] = pivot_cat["Entrada"] - pivot_cat["Saída"]
        for col in ["Entrada", "Saída", "Saldo"]:
            if col in pivot_cat.columns:
                pivot_cat[f"{col}_fmt"] = pivot_cat[col].apply(fmt_currency)
        cols_display = ["categoria"] + [f"{col}_fmt" for col in ["Entrada", "Saída", "Saldo"] if f"{col}_fmt" in pivot_cat.columns]
        st.dataframe(pivot_cat[cols_display], use_container_width=True, hide_index=True)
    with tab3:
        df_mensal = df_filtered.copy()
        df_mensal["data_dt"] = pd.to_datetime(df_mensal["data"], errors="coerce")
        df_mensal = df_mensal.dropna(subset=["data_dt"])
        df_mensal["mes_num"] = df_mensal["data_dt"].dt.month
        df_mensal["mes_nome"] = df_mensal["data_dt"].dt.strftime("%B")
        pivot_mensal = df_mensal.pivot_table(
            index=["mes_num", "mes_nome"],
            columns="tipo",
            values="valor",
            aggfunc="sum",
            fill_value=0
        ).reset_index()
        if "Entrada" in pivot_mensal.columns and "Saída" in pivot_mensal.columns:
            pivot_mensal["Saldo"] = pivot_mensal["Entrada"] - pivot_mensal["Saída"]
            pivot_mensal["Saldo_Acum"] = pivot_mensal["Saldo"].cumsum()
        fig_mensal = go.Figure()
        if "Entrada" in pivot_mensal.columns:
            fig_mensal.add_trace(go.Bar(
                name="Entradas",
                x=pivot_mensal["mes_nome"],
                y=pivot_mensal["Entrada"],
                marker_color="#2ca02c"
            ))
        if "Saída" in pivot_mensal.columns:
            fig_mensal.add_trace(go.Bar(
                name="Saídas",
                x=pivot_mensal["mes_nome"],
                y=pivot_mensal["Saída"],
                marker_color="#d62728"
            ))
        fig_mensal.update_layout(
            title=f"Movimentação Mensal - {ano_dash}",
            xaxis_title="Mês",
            yaxis_title="Valor (R$)",
            barmode="group",
            height=400
        )
        st.plotly_chart(fig_mensal, use_container_width=True)
        st.markdown("**🗓þ00 Tabela Mensal Detalhada**")
        pivot_display = pivot_mensal.copy()
        for col in ["Entrada", "Saída", "Saldo", "Saldo_Acum"]:
            if col in pivot_display.columns:
                pivot_display[f"{col}_fmt"] = pivot_display[col].apply(fmt_currency)
        cols_show = ["mes_nome"] + [f"{col}_fmt" for col in ["Entrada", "Saída", "Saldo", "Saldo_Acum"] if f"{col}_fmt" in pivot_display.columns]
        st.dataframe(
            pivot_display[cols_show], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "mes_nome": "Mês",
                "Entrada_fmt": "Entradas",
                "Saída_fmt": "Saídas",
                "Saldo_fmt": "Saldo",
                "Saldo_Acum_fmt": "Saldo Acumulado"
            }
        )
    st.markdown("### 📅 Exportar Dados")
    col1, col2, col3 = st.columns(3)
    with col1:
        csv_buffer = StringIO()
        df_filtered.to_csv(csv_buffer, index=False, sep=";", encoding="utf-8")
        st.download_button(
            "📄 Baixar CSV",
            data=csv_buffer.getvalue(),
            file_name=f"fluxo_caixa_{empresa_dash}_{ano_dash}.csv",
            mime="text/csv"
        )
    with col2:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_filtered.to_excel(writer, sheet_name='Lançamentos', index=False)
            if not df_cat.empty:
                pivot_cat.to_excel(writer, sheet_name='Por Categoria', index=False)
            if not pivot_mensal.empty:
                pivot_mensal.to_excel(writer, sheet_name='Por Mês', index=False)
        st.download_button(
            "📊 Baixar Excel",
            data=excel_buffer.getvalue(),
            file_name=f"relatorio_completo_{empresa_dash}_{ano_dash}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col3:
        relatorio_buffer = StringIO()
        relatorio_buffer.write(f"RELATÓRIO FINANCEIRO - {empresa_dash} - {ano_dash}\n")
        relatorio_buffer.write("=" * 50 + "\n\n")
        relatorio_buffer.write(f"Total de Entradas: {fmt_currency(kpis['entradas'])}\n")
        relatorio_buffer.write(f"Total de Saídas: {fmt_currency(kpis['saidas'])}\n")
        relatorio_buffer.write(f"Saldo Líquido: {fmt_currency(kpis['saldo'])}\n")
        relatorio_buffer.write(f"Total de Lançamentos: {kpis['total_lancamentos']}\n\n")
        relatorio_buffer.write(f"Tendência Entradas ({periodo_trend}m): {fmt_percentage(trends['trend_entradas'])}\n")
        relatorio_buffer.write(f"Tendência Saídas ({periodo_trend}m): {fmt_percentage(trends['trend_saidas'])}\n")
        relatorio_buffer.write(f"Tendência Saldo ({periodo_trend}m): {fmt_percentage(trends['trend_saldo'])}\n")
        st.download_button(
            "📋 Relatório Resumo",
            data=relatorio_buffer.getvalue(),
            file_name=f"resumo_{empresa_dash}_{ano_dash}.txt",
            mime="text/plain"
        )

def page_comparativo():
    st.subheader("📈 Análise Comparativa")
    manager = LancamentoManager(DB_PATH)
    analytics = AnalyticsEngine(manager)
    st.markdown("Compare o desempenho entre diferentes períodos e empresas")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📆 Período 1**")
        ano1 = st.selectbox("Ano 1", range(2020, datetime.now().year + 2), key="ano1")
        empresas = ["Todas"] + get_empresas_list(manager.read_lancamentos())
        empresa1 = st.selectbox("Empresa 1", empresas, key="emp1")
    with col2:
        st.markdown("**📆 Período 2**")
        ano2 = st.selectbox("Ano 2", range(2020, datetime.now().year + 2), index=1 if datetime.now().year > 2020 else 0, key="ano2")
        empresa2 = st.selectbox("Empresa 2", empresas, key="emp2")
    filtros1 = {"data_inicio": f"{ano1}-01-01", "data_fim": f"{ano1}-12-31"}
    filtros2 = {"data_inicio": f"{ano2}-01-01", "data_fim": f"{ano2}-12-31"}
    if empresa1 != "Todas":
        filtros1["empresa"] = empresa1
    if empresa2 != "Todas":
        filtros2["empresa"] = empresa2
    df1 = manager.read_lancamentos(filtros1)
    df2 = manager.read_lancamentos(filtros2)
    kpis1 = analytics.calcular_kpis(df1)
    kpis2 = analytics.calcular_kpis(df2)
    st.markdown("### 📈 Comparacao de Indicadores")
    col1, col2, col3, col4 = st.columns(4)
    def calc_variation(val1, val2):
        if val1 == 0:
            return 0 if val2 == 0 else 100
        return ((val2 - val1) / val1) * 100
    with col1:
        var_entradas = calc_variation(kpis1["entradas"], kpis2["entradas"])
        st.metric(
            "💰 Entradas",
            fmt_currency(kpis2["entradas"]),
            f"{fmt_percentage(var_entradas)} vs {ano1}"
        )
    with col2:
        var_saidas = calc_variation(kpis1["saidas"], kpis2["saidas"])
        st.metric(
            "💸 Saídas", 
            fmt_currency(kpis2["saidas"]),
            f"{fmt_percentage(var_saidas)} vs {ano1}"
        )
    with col3:
        var_saldo = calc_variation(kpis1["saldo"], kpis2["saldo"])
        st.metric(
            "💶 Saldo",
            fmt_currency(kpis2["saldo"]),
            f"{fmt_percentage(var_saldo)} vs {ano1}"
        )
    with col4:
        var_lanc = calc_variation(kpis1["total_lancamentos"], kpis2["total_lancamentos"])
        st.metric(
            "📊 Lançamentos",
            f"{kpis2['total_lancamentos']:,}".replace(",", "."),
            f"{fmt_percentage(var_lanc)} vs {ano1}"
        )
    if not df1.empty and not df2.empty:
        st.markdown("### 📈 Gráficos Comparativos")
        tab1, tab2 = st.tabs(["📈 Evolução Mensal", "🏢 Por Categoria"])
        with tab1:
            def prepare_monthly_data(df, year, label):
                df_temp = df.copy()
                df_temp["data_dt"] = pd.to_datetime(df_temp["data"], errors="coerce")
                df_temp = df_temp.dropna(subset=["data_dt"])
                df_temp["mes"] = df_temp["data_dt"].dt.month
                df_temp["tipo_norm"] = df_temp["tipo"].str.lower()
                monthly = df_temp.groupby(["mes", "tipo_norm"])["valor"].sum().unstack(fill_value=0)
                monthly = monthly.reindex(range(1, 13), fill_value=0)
                monthly["periodo"] = label
                monthly["ano"] = year
                return monthly.reset_index()
            monthly1 = prepare_monthly_data(df1, ano1, f"{empresa1} {ano1}")
            monthly2 = prepare_monthly_data(df2, ano2, f"{empresa2} {ano2}")
            fig_comp = go.Figure()
            if "entrada" in monthly1.columns:
                fig_comp.add_trace(go.Scatter(
                    x=monthly1["mes"], y=monthly1["entrada"],
                    name=f"Entradas {ano1}", line=dict(color="#2ca02c", dash="solid")
                ))
            if "saída" in monthly1.columns:
                fig_comp.add_trace(go.Scatter(
                    x=monthly1["mes"], y=monthly1["saída"],
                    name=f"Saídas {ano1}", line=dict(color="#d62728", dash="solid")
                ))
            if "entrada" in monthly2.columns:
                fig_comp.add_trace(go.Scatter(
                    x=monthly2["mes"], y=monthly2["entrada"],
                    name=f"Entradas {ano2}", line=dict(color="#2ca02c", dash="dash")
                ))
            if "saída" in monthly2.columns:
                fig_comp.add_trace(go.Scatter(
                    x=monthly2["mes"], y=monthly2["saída"],
                    name=f"Saídas {ano2}", line=dict(color="#d62728", dash="dash")
                ))
            fig_comp.update_layout(
                title="Comparacão de Evolução Mensal",
                xaxis_title="Mês",
                yaxis_title="Valor (R$)",
                height=500
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        with tab2:
            cat1 = df1.groupby("categoria")["valor"].sum().sort_values(ascending=False).head(10)
            cat2 = df2.groupby("categoria")["valor"].sum().sort_values(ascending=False).head(10)
            fig_cat_comp = go.Figure()
            categorias_comuns = list(set(cat1.index) & set(cat2.index))
            fig_cat_comp.add_trace(go.Bar(
                name=f"{ano1}",
                x=categorias_comuns,
                y=[cat1.get(cat, 0) for cat in categorias_comuns],
                marker_color="#1f77b4"
            ))
            fig_cat_comp.add_trace(go.Bar(
                name=f"{ano2}",
                x=categorias_comuns,
                y=[cat2.get(cat, 0) for cat in categorias_comuns],
                marker_color="#ff7f0e"
            ))
            fig_cat_comp.update_layout(
                title="Comparacão por Categoria (Top Categorias Comuns)",
                xaxis_title="Categoria",
                yaxis_title="Valor (R$)",
                barmode="group",
                height=400
            )
            fig_cat_comp.update_xaxes(tickangle=45)
            st.plotly_chart(fig_cat_comp, use_container_width=True)

def page_previsoes():
    st.subheader("🔮 Previsões e Projeções")
    manager = LancamentoManager(DB_PATH)
    st.markdown("Análise preditiva baseada no histórico de dados")
    col1, col2, col3 = st.columns(3)
    with col1:
        empresas = ["Todas"] + get_empresas_list(manager.read_lancamentos())
        empresa_prev = st.selectbox("Empresa", empresas)
    with col2:
        meses_historico = st.selectbox("Meses de Histórico", [6, 12, 24], index=1)
    with col3:
        meses_projecao = st.selectbox("Meses de Projeção", [3, 6, 12], index=1)
    data_inicio = (datetime.now() - timedelta(days=meses_historico * 30)).strftime("%Y-%m-%d")
    filtros: Dict[str, str] = {"data_inicio": data_inicio}
    if empresa_prev != "Todas":
        filtros["empresa"] = empresa_prev
    df_historico = manager.read_lancamentos(filtros)
    if df_historico.empty:
        st.warning("⚠️ Não há dados suficientes para fazer projeções")
        return
    df_hist = df_historico.copy()
    df_hist["data_dt"] = pd.to_datetime(df_hist["data"], errors="coerce")
    df_hist = df_hist.dropna(subset=["data_dt"])
    df_hist["mes"] = df_hist["data_dt"].dt.to_period("M")
    df_hist["tipo_norm"] = df_hist["tipo"].str.lower()
    monthly_hist = df_hist.groupby(["mes", "tipo_norm"])["valor"].sum().unstack(fill_value=0)
    if monthly_hist.empty:
        st.warning("⚠️ Não há dados mensais suficientes para projeção")
        return
    entradas_media = monthly_hist.get("entrada", pd.Series()).mean()
    saidas_media = monthly_hist.get("saída", pd.Series()).mean()
    # usar numpy.polyfit para ajustar linha
    x = np.arange(len(monthly_hist))
    def _fit(y: pd.Series) -> Tuple[float, float]:
        y_arr = y.to_numpy(dtype=float)
        if len(y_arr) >= 2 and np.any(np.isfinite(y_arr)):
            slope, intercept = np.polyfit(x, y_arr, 1)
            return float(slope), float(intercept)
        return 0.0, float(np.nanmean(y_arr) if len(y_arr) else 0.0)
    if "entrada" in monthly_hist.columns:
        slope_ent, intercept_ent = _fit(monthly_hist["entrada"])
    else:
        slope_ent, intercept_ent = 0.0, 0.0
    if "saída" in monthly_hist.columns:
        slope_sai, intercept_sai = _fit(monthly_hist["saída"])
    else:
        slope_sai, intercept_sai = 0.0, 0.0
    projecoes: List[Dict[str, float]] = []
    last_month = monthly_hist.index.max()
    for i in range(1, meses_projecao + 1):
        next_month = last_month + i
        ent_proj = intercept_ent + slope_ent * (len(monthly_hist) + i - 1)
        sai_proj = intercept_sai + slope_sai * (len(monthly_hist) + i - 1)
        ent_proj = max(0, ent_proj)
        sai_proj = max(0, sai_proj)
        projecoes.append({
            "mes": next_month,
            "entradas_proj": ent_proj,
            "saidas_proj": sai_proj,
            "saldo_proj": ent_proj - sai_proj
        })
    df_proj = pd.DataFrame(projecoes)
    st.markdown("### 📈 Projeções Calculadas")
    col1, col2, col3, col4 = st.columns(4)
    total_ent_proj = df_proj["entradas_proj"].sum()
    total_sai_proj = df_proj["saidas_proj"].sum()
    saldo_proj = total_ent_proj - total_sai_proj
    with col1:
        st.metric("💰 Entradas Projetadas", fmt_currency(total_ent_proj))
    with col2:
        st.metric("💸 Saídas Projetadas", fmt_currency(total_sai_proj))
    with col3:
        st.metric("💶 Saldo Projetado", fmt_currency(saldo_proj))
    with col4:
        roi_proj = (saldo_proj / total_sai_proj * 100) if total_sai_proj > 0 else 0
        st.metric("📈 ROI Projetado", fmt_percentage(roi_proj))
    st.markdown("### 💻 Histórico vs Projeções")
    fig_prev = go.Figure()
    hist_dates = [str(m) for m in monthly_hist.index]
    if "entrada" in monthly_hist.columns:
        fig_prev.add_trace(go.Scatter(
            x=hist_dates,
            y=monthly_hist["entrada"],
            name="Entradas (Histórico)",
            line=dict(color="#2ca02c", width=3),
            mode="lines+markers"
        ))
    if "saída" in monthly_hist.columns:
        fig_prev.add_trace(go.Scatter(
            x=hist_dates,
            y=monthly_hist["saída"],
            name="Saídas (Histórico)",
            line=dict(color="#d62728", width=3),
            mode="lines+markers"
        ))
    proj_dates = [str(m) for m in df_proj["mes"]]
    fig_prev.add_trace(go.Scatter(
        x=proj_dates,
        y=df_proj["entradas_proj"],
        name="Entradas (Projetadas)",
        line=dict(color="#2ca02c", width=2, dash="dash"),
        mode="lines+markers"
    ))
    fig_prev.add_trace(go.Scatter(
        x=proj_dates,
        y=df_proj["saidas_proj"],
        name="Saídas (Projetadas)",
        line=dict(color="#d62728", width=2, dash="dash"),
        mode="lines+markers"
    ))
    fig_prev.update_layout(
        title=f"Projeção Financeira - {empresa_prev} ({meses_projecao} meses)",
        xaxis_title="Período",
        yaxis_title="Valor (R$)",
        height=500,
        hovermode="x unified"
    )
    st.plotly_chart(fig_prev, use_container_width=True)
    st.markdown("### 📃 Tabela de Projeções Detalhada")
    df_proj_display = df_proj.copy()
    df_proj_display["Período"] = df_proj_display["mes"].astype(str)
    df_proj_display["Entradas"] = df_proj_display["entradas_proj"].apply(fmt_currency)
    df_proj_display["Saídas"] = df_proj_display["saidas_proj"].apply(fmt_currency)
    df_proj_display["Saldo"] = df_proj_display["saldo_proj"].apply(fmt_currency)
    df_proj_display["Saldo Acumulado"] = df_proj_display["saldo_proj"].cumsum().apply(fmt_currency)
    st.dataframe(
        df_proj_display[["Período", "Entradas", "Saídas", "Saldo", "Saldo Acumulado"]],
        use_container_width=True,
        hide_index=True
    )
    st.markdown("### 🇺🇸 Insights e Recomendações")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📈 Análise da Tendência**")
        if slope_ent > 0:
            st.success(f"✅ Entradas em crescimento: +{fmt_percentage(abs(slope_ent/entradas_media*100))}/mês")
        elif slope_ent < 0:
            st.warning(f"⚠️ Entradas em declínio: {fmt_percentage(slope_ent/entradas_media*100)}/mês")
        else:
            st.info("➡️ Entradas estáveis")
        if slope_sai > 0:
            st.warning(f"⚠️ Saídas em crescimento: +{fmt_percentage(abs(slope_sai/saidas_media*100))}/mês")
        elif slope_sai < 0:
            st.success(f"✅ Saídas em redução: {fmt_percentage(slope_sai/saidas_media*100)}/mês")
        else:
            st.info("➡️ Saídas estáveis")
    with col2:
        st.markdown("**📝 Recomendações**")
        if saldo_proj < 0:
            st.error("🚨 Saldo projetado negativo! Considere:")
            st.write("\u2022 Reduzir custos operacionais")
            st.write("\u2022 Aumentar receitas")
            st.write("\u2022 Renegociar fornecedores")
        elif saldo_proj > 0:
            st.success("✅ Projeção positiva! Oportunidades:")
            st.write("\u2022 Investir em crescimento")
            st.write("\u2022 Criar reserva de emergência")
            st.write("\u2022 Expandir operações")
        margem_seguranca = (saldo_proj / total_ent_proj * 100) if total_ent_proj > 0 else 0
        if margem_seguranca < 10:
            st.warning("⚠️ Margem de segurança baixa")
        else:
            st.info(f"📈 Margem de segurança: {fmt_percentage(margem_seguranca)}")

def seed_database_if_empty():
    manager = LancamentoManager(DB_PATH)
    df_existing = manager.read_lancamentos()
    if not df_existing.empty:
        return
    today = date.today()
    start_date = date(today.year - 1, 1, 1)
    empresas_seed = EMPRESAS_PADRAO
    categorias_ent_seed = CATEGORIAS_ENTRADA[:4]
    categorias_sai_seed = CATEGORIAS_SAIDA[:6]
    import random
    random.seed(42)
    current_date = start_date
    while current_date <= today:
        for empresa in empresas_seed:
            for _ in range(random.randint(2, 4)):
                valor_entrada = random.uniform(800, 3000)
                categoria = random.choice(categorias_ent_seed)
                manager.insert_lancamento({
                    "data": current_date.isoformat(),
                    "empresa": empresa,
                    "descricao": f"Receita de {categoria.lower()}",
                    "categoria": categoria,
                    "tipo": "Entrada",
                    "valor": valor_entrada,
                    "observacoes": f"Lançamento automático - {categoria}"
                })
            for _ in range(random.randint(3, 6)):
                valor_saida = random.uniform(300, 1500)
                categoria = random.choice(categorias_sai_seed)
                manager.insert_lancamento({
                    "data": current_date.isoformat(),
                    "empresa": empresa,
                    "descricao": f"Pagamento de {categoria.lower()}",
                    "categoria": categoria,
                    "tipo": "Saída",
                    "valor": valor_saida,
                    "observacoes": f"Lançamento automático - {categoria}"
                })
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)

def main():
    seed_database_if_empty()
    st.title("💸 Sistema de Fluxo de Caixa Profissional")
    st.markdown("*Gestão financeira completa com análises avançadas e projeções*")
    with st.sidebar:
        st.markdown("## 🤎 Navegação")
        page = st.radio(
            "Selecione uma página:",
            [
                "📥 Lançamentos",
                "📈 Dashboard",
                "📈 Comparativo",
                "🔮 Projeções"
            ],
            index=0
        )
        st.divider()
        with st.expander("ℹ️ Informações do Sistema"):
            manager = LancamentoManager(DB_PATH)
            df_total = manager.read_lancamentos()
            if not df_total.empty:
                total_registros = len(df_total)
                empresas_ativas = df_total["empresa"].nunique()
                data_mais_antiga = df_total["data"].min()
                data_mais_recente = df_total["data"].max()
                st.write(f"**📈 Total de registros:** {total_registros:,}".replace(",", "."))
                st.write(f"**🏢 Empresas ativas:** {empresas_ativas}")
                st.write(f"**📅 Período:** {data_mais_antiga} a {data_mais_recente}")
            else:
                st.write("Nenhum dado disponível")
        st.markdown("---")
        st.markdown("**v2.0** - Sistema Profissional")
        st.markdown("*Desenvolvido com Streamlit*")
    if page == "📥 Lançamentos":
        page_lancamentos()
    elif page == "📈 Dashboard":
        page_dashboard()
    elif page == "📈 Comparativo":
        page_comparativo()
    elif page == "🔮 Projeções":
        page_previsoes()

if __name__ == "__main__":
    main()
