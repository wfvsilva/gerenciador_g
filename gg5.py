import streamlit as st
import pandas as pd
import json
import os
import openrouteservice
import folium
import gspread
from datetime import date
from streamlit_folium import st_folium

# Endereço de partida padrão para entregas
ENDERECO_PARTIDA = "Rua Doutor Clemente Ferreira, São Caetano do Sul,SP,Brasil"

# === Insira sua chave da OpenRouteService aqui ===
ORS_API_KEY = "5b3ce3597851110001cf624819bd5deaa11e47e6a5b39d6f0c2ce4b4"  # https://openrouteservice.org

# Iniciar o cliente da rota
try:
    ors = openrouteservice.Client(key=ORS_API_KEY)
except:
    ors = None

# ========== FUNÇÕES DE CONEXÃO E GERENCIAMENTO DO GOOGLE SHEETS ==========

class GoogleSheetsManager:
    """Gerencia a conexão e operações com o Google Sheets."""
    def __init__(self, spreadsheet_name):
        self.spreadsheet_name = spreadsheet_name
        self._gc = None
        self._spreadsheet = None
        self._connect()

    def _connect(self):
        """Estabelece a conexão com a conta de serviço e a planilha."""
        try:
            self._gc = gspread.service_account_from_dict(st.secrets["GOOGLE_CREDENTIALS"])
            self._spreadsheet = self._gc.open(self.spreadsheet_name)
        except Exception as e:
            st.error(f"Erro ao conectar com o Google Sheets. Verifique o nome da planilha e a credencial no secrets.toml. Erro: {e}")
            st.stop()
            
    def get_dataframe(self, worksheet_name):
        """Carrega os dados de uma aba em um DataFrame do pandas."""
        try:
            worksheet = self._spreadsheet.worksheet(worksheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except gspread.exceptions.WorksheetNotFound:
            st.warning(f"A aba '{worksheet_name}' não foi encontrada na planilha. Criando nova aba...")
            worksheet = self._spreadsheet.add_worksheet(title=worksheet_name, rows=1, cols=1)
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Erro ao ler dados da aba '{worksheet_name}'. Erro: {e}")
            return pd.DataFrame()
        
    def append_row(self, worksheet_name, data):
        """Adiciona uma nova linha a uma aba."""
        try:
            worksheet = self._spreadsheet.worksheet(worksheet_name)
            # Converte valores do dicionário para uma lista na ordem correta
            row_values = list(data.values())
            worksheet.append_row(row_values)
            return True
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"A aba '{worksheet_name}' não foi encontrada.")
            return False
        except Exception as e:
            st.error(f"Erro ao adicionar dados à aba '{worksheet_name}'. Verifique se as colunas estão corretas. Erro: {e}")
            return False

    def update_data(self, worksheet_name, df):
        """Atualiza a aba inteira com um DataFrame."""
        try:
            worksheet = self._spreadsheet.worksheet(worksheet_name)
            worksheet.clear()
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar dados na aba '{worksheet_name}'. Erro: {e}")
            return False

    def list_worksheets(self):
        """Lista todas as abas da planilha."""
        return [ws.title for ws in self._spreadsheet.worksheets()]

# Inicializa o gerenciador do Google Sheets
SHEETS_MANAGER = GoogleSheetsManager("GGApp") # <<<< SUBSTITUA PELO NOME DA SUA PLANILHA

# ========== FUNÇÕES DE CADA ABA ==========
def aba_producao():
    st.header("📅 Registro Diário de Produção")

    # Carrega dados
    df = SHEETS_MANAGER.get_dataframe("producao")
    
    with st.form("form_producao"):
        data = st.date_input("Data", value=date.today())
        ovos = st.number_input("Ovos coletados", min_value=0)
        galinhas = st.number_input("Galinhas em postura", min_value=0, max_value=200)
        vendas = st.number_input("Valor das vendas (R$)", min_value=0.0, format="%.2f")
        mortes = st.number_input("Número de galinhas mortas", min_value=0)
        
        submit_button = st.form_submit_button("Salvar produção")

    if submit_button:
        novo_dado = {
            "Data": str(data),
            "Ovos": ovos,
            "Galinhas em Postura": galinhas,
            "Vendas (R$)": vendas,
            "Mortes": mortes
        }
        if SHEETS_MANAGER.append_row("producao", novo_dado):
            st.success("✅ Registro salvo!")
            st.rerun()

    st.subheader("📋 Histórico de Produção")
    st.dataframe(df, use_container_width=True)

def aba_custos():
    st.header("💰 Lançamento de Custos")

    df = SHEETS_MANAGER.get_dataframe("custos")

    with st.form("form_custos"):
        data = st.date_input("Data do custo", value=date.today())
        categoria = st.selectbox("Categoria", ["Ração", "Vacinas", "Mão de obra", "Energia", "Outros"])
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")

        submit_button = st.form_submit_button("Salvar custo")

    if submit_button:
        novo_dado = {
            "Data": str(data),
            "Categoria": categoria,
            "Descrição": descricao,
            "Valor (R$)": valor
        }
        if SHEETS_MANAGER.append_row("custos", novo_dado):
            st.success("✅ Custo registrado!")
            st.rerun()

    st.subheader("📋 Histórico de Custos")
    st.dataframe(df, use_container_width=True)

def aba_relatorios():
    st.header("📊 Indicadores Gerais")

    df_producao = SHEETS_MANAGER.get_dataframe("producao")
    df_custos = SHEETS_MANAGER.get_dataframe("custos")

    if not df_producao.empty:
        df_producao["Vendas (R$)"] = pd.to_numeric(df_producao["Vendas (R$)"], errors='coerce')
        df_producao["Ovos"] = pd.to_numeric(df_producao["Ovos"], errors='coerce')
        df_producao["Galinhas em Postura"] = pd.to_numeric(df_producao["Galinhas em Postura"], errors='coerce')

        media_ovos = df_producao["Ovos"].mean()
        taxa = (df_producao["Ovos"].sum() / df_producao["Galinhas em Postura"].sum()) * 100 if df_producao["Galinhas em Postura"].sum() > 0 else 0
        total_vendas = df_producao["Vendas (R$)"].sum()

        st.metric("Produção Média de Ovos", f"{media_ovos:.1f}")
        st.metric("Taxa de Postura Média", f"{taxa:.1f}%")
        st.metric("Total de Vendas", f"R$ {total_vendas:.2f}")

    if not df_custos.empty:
        df_custos["Valor (R$)"] = pd.to_numeric(df_custos["Valor (R$)"], errors='coerce')
        total_custos = df_custos["Valor (R$)"].sum()
        st.metric("Total de Custos", f"R$ {total_custos:.2f}")

        if not df_producao.empty:
            lucro = total_vendas - total_custos
            st.metric("Lucro Estimado", f"R$ {lucro:.2f}")

def aba_fechamento():
    st.header("📆 Fechamento do Mês")

    df_producao = SHEETS_MANAGER.get_dataframe("producao")
    df_custos = SHEETS_MANAGER.get_dataframe("custos")
    
    if not df_producao.empty:
        df_producao["Data"] = pd.to_datetime(df_producao["Data"])
        df_producao["Ano-Mês"] = df_producao["Data"].dt.to_period("M")

        resumo_prod = df_producao.groupby("Ano-Mês").agg({
            "Ovos": ["sum", "mean"],
            "Galinhas em Postura": "sum",
            "Vendas (R$)": "sum"
        }).reset_index()
        resumo_prod.columns = ["Ano-Mês", "Total Ovos", "Média Ovos", "Total Galinhas", "Total Vendas"]
        resumo_prod["Taxa de Postura (%)"] = (resumo_prod["Total Ovos"] / resumo_prod["Total Galinhas"].replace(0, 1)) * 100

        if not df_custos.empty:
            df_custos["Data"] = pd.to_datetime(df_custos["Data"])
            df_custos["Ano-Mês"] = df_custos["Data"].dt.to_period("M")
            resumo_custos = df_custos.groupby("Ano-Mês")["Valor (R$)"].sum().reset_index()
            resumo_custos.columns = ["Ano-Mês", "Total Custos"]
            fechamento = pd.merge(resumo_prod, resumo_custos, on="Ano-Mês", how="left").fillna(0)
            fechamento["Lucro (R$)"] = fechamento["Total Vendas"] - fechamento["Total Custos"]
        else:
            fechamento = resumo_prod
            fechamento["Total Custos"] = 0.0
            fechamento["Lucro (R$)"] = fechamento["Total Vendas"]

        st.dataframe(fechamento, use_container_width=True)
    else:
        st.info("Nenhum dado de produção encontrado.")

# ======== A FAZERES (KANBAN) =========
def aba_tarefas():
    st.header("📌 Quadro de Tarefas (Kanban com Post-its)")
    
    df_tarefas = SHEETS_MANAGER.get_dataframe("tarefas")
    if df_tarefas.empty:
        tarefas = {"a_fazer": [], "feito": []}
    else:
        tarefas = {
            "a_fazer": df_tarefas[df_tarefas["Status"] == "A Fazer"]["Tarefa"].tolist(),
            "feito": df_tarefas[df_tarefas["Status"] == "Feito"]["Tarefa"].tolist()
        }

    with st.form("nova_tarefa"):
        nova = st.text_input("Nova tarefa")
        enviar = st.form_submit_button("Adicionar")
    if enviar and nova:
        if SHEETS_MANAGER.append_row("tarefas", {"Tarefa": nova, "Status": "A Fazer"}):
            st.success("Tarefa adicionada!")
            st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🕒 A Fazer")
        for t in tarefas["a_fazer"]:
            st.markdown(f"""
                <div style='
                    background-color: #fff8b3;
                    border-radius: 8px;
                    padding: 10px;
                    margin-bottom: 8px;
                    box-shadow: 1px 1px 5px rgba(0,0,0,0.1);
                    font-weight: bold;
                '>{t}</div>
            """, unsafe_allow_html=True)
        selecionadas_mover = st.multiselect("Mover para Feito ✅:", tarefas["a_fazer"], key="a_fazer_select")

        if st.button("Confirmar movimento", key="btn_mover"):
            df_tarefas_atualizada = df_tarefas.copy()
            for t in selecionadas_mover:
                df_tarefas_atualizada.loc[df_tarefas_atualizada["Tarefa"] == t, "Status"] = "Feito"
            
            if SHEETS_MANAGER.update_data("tarefas", df_tarefas_atualizada):
                st.rerun()

    with col2:
        st.subheader("✔️ Feito")
        for t in tarefas["feito"]:
            st.markdown(f"""
                <div style='
                    background-color: #d2f8d2;
                    border-radius: 8px;
                    padding: 10px;
                    margin-bottom: 8px;
                    box-shadow: 1px 1px 5px rgba(0,0,0,0.1);
                    font-weight: bold;
                    text-decoration: line-through;
                '>{t}</div>
            """, unsafe_allow_html=True)
        selecionadas_voltar = st.multiselect("Voltar para A Fazer 🔁:", tarefas["feito"], key="feito_select")

        if st.button("Voltar selecionadas", key="btn_voltar"):
            df_tarefas_atualizada = df_tarefas.copy()
            for t in selecionadas_voltar:
                df_tarefas_atualizada.loc[df_tarefas_atualizada["Tarefa"] == t, "Status"] = "A Fazer"

            if SHEETS_MANAGER.update_data("tarefas", df_tarefas_atualizada):
                st.rerun()

# ======== CLIENTES =========
def aba_clientes():
    st.header("📋 Cadastro de Clientes")

    with st.form("form_clientes"):
        nome = st.text_input("Nome do Cliente")
        endereco = st.text_input("Endereço Completo")
        
        submit_button = st.form_submit_button("Adicionar Cliente")

    if submit_button:
        if nome and endereco:
            novo_cliente = {"nome": nome, "endereco": endereco}
            if SHEETS_MANAGER.append_row("clientes", novo_cliente):
                st.success("Cliente adicionado!")
                st.rerun()
        else:
            st.warning("Preencha os dois campos.")

    st.subheader("📁 Lista de Clientes")
    df_clientes = SHEETS_MANAGER.get_dataframe("clientes")
    if not df_clientes.empty:
        for index, row in df_clientes.iterrows():
            st.write(f"**{row['nome']}** — {row['endereco']}")


# ======== ROTA =========
def geocodificar_endereco(endereco, nome):
    try:
        resposta = ors.pelias_search(text=endereco)
        coords = resposta["features"][0]["geometry"]["coordinates"]
        return coords
    except Exception:
        st.warning(f"Erro ao localizar endereço: {nome}")
        return None

def aba_rota():
    st.header("🚚 Geração de Rota de Entrega")

    df_clientes = SHEETS_MANAGER.get_dataframe("clientes")
    if df_clientes.empty:
        st.info("Cadastre clientes antes de gerar a rota.")
        return

    selecionados = st.multiselect("Selecione os clientes com pedido:", [f"{row['nome']} – {row['endereco']}" for index, row in df_clientes.iterrows()])
    if not selecionados:
        return

    partida = st.text_input("Endereço de partida:", value=ENDERECO_PARTIDA)

    if not ors:
        st.error("Insira uma chave válida da OpenRouteService no código.")
        return

    if st.button("Gerar Rota Otimizada"):
        coordenadas = []
        nomes = []

        coord_partida = geocodificar_endereco(partida, "Partida")
        if not coord_partida:
            st.stop()
        coordenadas.append(coord_partida)
        nomes.append("Partida")

        for s in selecionados:
            c = df_clientes[df_clientes.apply(lambda row: f"{row['nome']} – {row['endereco']}" == s, axis=1)].iloc[0]
            coord = geocodificar_endereco(c["endereco"], c["nome"])
            if coord:
                coordenadas.append(coord)
                nomes.append(c["nome"])

        st.session_state["rota_coords"] = coordenadas
        st.session_state["rota_nomes"] = nomes
        st.session_state["mostrar_rota"] = True

    if st.session_state.get("mostrar_rota", False):
        try:
            coordenadas = st.session_state["rota_coords"]
            nomes = st.session_state["rota_nomes"]

            rotas = ors.directions(
                coordinates=coordenadas,
                profile="driving-car",
                format="geojson",
                optimize_waypoints=len(coordenadas) >= 4
            )

            distancia = rotas["features"][0]["properties"]["segments"][0]["distance"] / 1000
            duracao = rotas["features"][0]["properties"]["segments"][0]["duration"] / 60
            st.success(f"Distância: {distancia:.2f} km | Tempo: {duracao:.1f} min")

            m = folium.Map(location=coordenadas[0][::-1], zoom_start=12)
            folium.Marker(coordenadas[0][::-1], tooltip="Partida", icon=folium.Icon(color="green")).add_to(m)
            for i, coord in enumerate(coordenadas[1:], 1):
                folium.Marker(coord[::-1], tooltip=nomes[i], icon=folium.Icon(color="blue")).add_to(m)
            folium.PolyLine([c[::-1] for c in coordenadas], color="blue").add_to(m)
            st_folium(m, width=700, height=500)

            if len(coordenadas) >= 2:
                google_maps_url = f"https://www.google.com/maps/dir/{coordenadas[0][1]},{coordenadas[0][0]}" + "".join(
                    [f"/{coord[1]},{coord[0]}" for coord in coordenadas[1:]]
                )
                waze_url = f"https://waze.com/ul?ll={coordenadas[-1][1]},{coordenadas[-1][0]}&navigate=yes"

                st.markdown(f"**🗺️ Google Maps:** [Abrir Rota]({google_maps_url})", unsafe_allow_html=True)
                st.markdown(f"**🚗 Waze (último destino):** [Abrir Rota]({waze_url})", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Erro ao gerar rota: {e}")

# ======== CRIAR PEDIDOS =========
def aba_pedidos():
    st.header("🧾 Criar pedidos da semana")

    if "data_inicio" not in st.session_state:
        st.session_state["data_inicio"] = date.today()
    if "data_fim" not in st.session_state:
        st.session_state["data_fim"] = date.today()

    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Início da Semana", value=st.session_state["data_inicio"], format="DD/MM/YYYY")
        st.session_state["data_inicio"] = data_inicio
    with col2:
        data_fim = st.date_input("Fim da Semana", value=st.session_state["data_fim"], format="DD/MM/YYYY")
        st.session_state["data_fim"] = data_fim

    nome_aba = f"pedidos_{data_inicio.strftime('%d-%m')} a {data_fim.strftime('%d-%m')}"

    valor_base = st.number_input("💵 Valor Base da Cartela (R$)", min_value=0.0, format="%.2f")

    df_clientes = SHEETS_MANAGER.get_dataframe("clientes")
    if df_clientes.empty:
        st.info("Cadastre clientes antes de registrar pedidos.")
        return
    nomes_clientes = df_clientes["nome"].tolist()

    st.subheader("📋 Novo Pedido")
    cliente = st.selectbox("Cliente", nomes_clientes)
    qnt_cartelas = st.number_input("Quantidade de Cartelas", min_value=1, step=1)
    forma_pgto = st.selectbox("Forma de Pagamento", ["Dinheiro", "Cartão", "Pix"])
    pago = st.checkbox("✅ Pago")

    valor_total = qnt_cartelas * valor_base
    st.write(f"💰 Valor Total: R$ {valor_total:.2f}")

    if st.button("Salvar Pedido"):
        novo_pedido = {
            "Cliente": cliente,
            "Cartelas": qnt_cartelas,
            "Valor Base": valor_base,
            "Valor Total": valor_total,
            "Forma de Pagamento": forma_pgto,
            "Pago": "Sim" if pago else "Não"
        }
        
        # Cria a aba se não existir
        try:
            worksheet = SHEETS_MANAGER._spreadsheet.worksheet(nome_aba)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = SHEETS_MANAGER._spreadsheet.add_worksheet(title=nome_aba, rows=1, cols=len(novo_pedido))
            # Adiciona os cabeçalhos
            worksheet.append_row(list(novo_pedido.keys()))

        if SHEETS_MANAGER.append_row(nome_aba, novo_pedido):
            st.success("✅ Pedido salvo com sucesso!")

# ======== VISUALIZAR PEDIDOS =========
def aba_visualizar_pedidos():
    st.header("📂 Visualizar Pedidos Salvos")
    
    # Lista apenas as abas que são de pedidos
    abas_pedidos = [aba for aba in SHEETS_MANAGER.list_worksheets() if aba.startswith("pedidos_")]
    
    if not abas_pedidos:
        st.info("Nenhum pedido da semana foi salvo ainda.")
        return

    aba_selecionada = st.selectbox("Selecione o intervalo da semana:", abas_pedidos)

    if aba_selecionada:
        df = SHEETS_MANAGER.get_dataframe(aba_selecionada)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenhum dado encontrado para esta semana.")

# ======== APP PRINCIPAL =========
st.set_page_config(page_title="Gestão de Galinheiro e Entregas", layout="wide")

st.title("🐔 Gerenciamento de Granja")

menu = st.sidebar.radio("📚 Navegar entre seções:", [
    "📅 Produção Diária",
    "💰 Lançamento de Custos",
    "📊 Relatórios",
    "📆 Fechamento do Mês",
    "📌 A Fazeres",
    "📋 Clientes",
    "🚚 Rota",
    "🧾 Criar Pedidos da Semana",
    "🧾 Ver Pedidos da Semana",
])

if menu == "📅 Produção Diária":
    aba_producao()

elif menu == "💰 Lançamento de Custos":
    aba_custos()

elif menu == "📊 Relatórios":
    aba_relatorios()

elif menu == "📆 Fechamento do Mês":
    aba_fechamento()

elif menu == "📌 A Fazeres":
    aba_tarefas()

elif menu == "📋 Clientes":
    aba_clientes()

elif menu == "🚚 Rota":
    aba_rota()
    
elif menu == "🧾 Criar Pedidos da Semana":
    aba_pedidos()

elif menu == "🧾 Ver Pedidos da Semana":
    aba_visualizar_pedidos()
