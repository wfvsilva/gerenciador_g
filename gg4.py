import streamlit as st
import pandas as pd
import json
import os
import openrouteservice
import folium
from datetime import date
from streamlit_folium import st_folium
from pathlib import Path

# ========== CONFIGURAÇÕES ==========
# Arquivos locais
ARQ_PRODUCAO = "producao.xlsx"
ARQ_CUSTOS = "custos.xlsx"
ARQ_TAREFAS = "tarefas.json"
ARQ_CLIENTES = "clientes.json"

# Endereço de partida padrão para entregas
ENDERECO_PARTIDA = "Rua Doutor Clemente Ferreira, São Caetano do Sul,SP,Brasil"

# === Insira sua chave da OpenRouteService aqui ===
ORS_API_KEY = "5b3ce3597851110001cf624819bd5deaa11e47e6a5b39d6f0c2ce4b4"  # https://openrouteservice.org

# Iniciar o cliente da rota
try:
    ors = openrouteservice.Client(key=ORS_API_KEY)
except:
    ors = None

# ========== FUNÇÕES COMUNS ==========

def carregar_dados_excel(arquivo, colunas):
    if os.path.exists(arquivo):
        return pd.read_excel(arquivo)
    else:
        df = pd.DataFrame(columns=colunas)
        df.to_excel(arquivo, index=False)
        return df

def salvar_dado_excel(arquivo, novo_dado):
    df = carregar_dados_excel(arquivo, list(novo_dado.keys()))
    df = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)
    df.to_excel(arquivo, index=False)

def carregar_json(caminho, vazio=None):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return vazio if vazio is not None else {}

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

# ========== FUNÇÕES DE CADA ABA ==========
def aba_producao():
    st.header("📅 Registro Diário de Produção")

    data = st.date_input("Data", value=date.today())
    ovos = st.number_input("Ovos coletados", min_value=0)
    galinhas = st.number_input("Galinhas em postura", min_value=0, max_value=200)
    vendas = st.number_input("Valor das vendas (R$)", min_value=0.0, format="%.2f")
    mortes = st.number_input("Número de galinhas mortas", min_value=0)

    if st.button("Salvar produção"):
        salvar_dado_excel(ARQ_PRODUCAO, {
            "Data": data,
            "Ovos": ovos,
            "Galinhas em Postura": galinhas,
            "Vendas (R$)": vendas,
            "Mortes": mortes
        })
        st.success("✅ Registro salvo!")

    df = carregar_dados_excel(ARQ_PRODUCAO, ["Data", "Ovos", "Galinhas em Postura", "Vendas (R$)", "Mortes"])
    st.subheader("📋 Histórico de Produção")
    st.dataframe(df, use_container_width=True)

def aba_custos():
    st.header("💰 Lançamento de Custos")

    data = st.date_input("Data do custo", value=date.today())
    categoria = st.selectbox("Categoria", ["Ração", "Vacinas", "Mão de obra", "Energia", "Outros"])
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")

    if st.button("Salvar custo"):
        salvar_dado_excel(ARQ_CUSTOS, {
            "Data": data,
            "Categoria": categoria,
            "Descrição": descricao,
            "Valor (R$)": valor
        })
        st.success("✅ Custo registrado!")

    df = carregar_dados_excel(ARQ_CUSTOS, ["Data", "Categoria", "Descrição", "Valor (R$)"])
    st.subheader("📋 Histórico de Custos")
    st.dataframe(df, use_container_width=True)

def aba_relatorios():
    st.header("📊 Indicadores Gerais")

    df_producao = carregar_dados_excel(ARQ_PRODUCAO, ["Data", "Ovos", "Galinhas em Postura", "Vendas (R$)", "Mortes"])
    df_custos = carregar_dados_excel(ARQ_CUSTOS, ["Data", "Categoria", "Descrição", "Valor (R$)"])

    if not df_producao.empty:
        media_ovos = df_producao["Ovos"].mean()
        taxa = (df_producao["Ovos"].sum() / df_producao["Galinhas em Postura"].sum()) * 100 if df_producao["Galinhas em Postura"].sum() > 0 else 0
        total_vendas = df_producao["Vendas (R$)"].sum()

        st.metric("Produção Média de Ovos", f"{media_ovos:.1f}")
        st.metric("Taxa de Postura Média", f"{taxa:.1f}%")
        st.metric("Total de Vendas", f"R$ {total_vendas:.2f}")

    if not df_custos.empty:
        total_custos = df_custos["Valor (R$)"].sum()
        st.metric("Total de Custos", f"R$ {total_custos:.2f}")

        if not df_producao.empty:
            lucro = total_vendas - total_custos
            st.metric("Lucro Estimado", f"R$ {lucro:.2f}")

def aba_fechamento():
    st.header("📆 Fechamento do Mês")

    df_producao = carregar_dados_excel(ARQ_PRODUCAO, ["Data", "Ovos", "Galinhas em Postura", "Vendas (R$)", "Mortes"])
    df_custos = carregar_dados_excel(ARQ_CUSTOS, ["Data", "Categoria", "Descrição", "Valor (R$)"])

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

        st.markdown("""
            <style>
                div[data-testid="stMainBlock"] {
                    max-width: 1080px;
                    margin: auto;
                }
                .element-container:has(.stDataFrame) div[data-testid="stVerticalBlock"] {
                    overflow: visible !important;
                    max-height: none !important;
                }
            </style>
        """, unsafe_allow_html=True)

        st.dataframe(fechamento, use_container_width=True)
    else:
        st.info("Nenhum dado de produção encontrado.")

# ======== A FAZERES (KANBAN) =========
def aba_tarefas():
    st.header("📌 Quadro de Tarefas (Kanban com Post-its)")

    tarefas = carregar_json(ARQ_TAREFAS, {"a_fazer": [], "feito": []})

    with st.form("nova_tarefa"):
        nova = st.text_input("Nova tarefa")
        enviar = st.form_submit_button("Adicionar")
        if enviar and nova:
            tarefas["a_fazer"].append(nova)
            salvar_json(ARQ_TAREFAS, tarefas)
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
        selecionadas = st.multiselect("Mover para Feito ✅:", tarefas["a_fazer"], key="a_fazer_select")
        if st.button("Confirmar movimento"):
            for t in selecionadas:
                tarefas["a_fazer"].remove(t)
                tarefas["feito"].append(t)
            salvar_json(ARQ_TAREFAS, tarefas)
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
        selecionadas = st.multiselect("Voltar para A Fazer 🔁:", tarefas["feito"], key="feito_select")
        if st.button("Voltar selecionadas"):
            for t in selecionadas:
                tarefas["feito"].remove(t)
                tarefas["a_fazer"].append(t)
            salvar_json(ARQ_TAREFAS, tarefas)
            st.rerun()

# ======== CLIENTES =========
def aba_clientes():
    st.header("📋 Cadastro de Clientes")

    nome = st.text_input("Nome do Cliente")
    endereco = st.text_input("Endereço Completo")

    if st.button("Adicionar Cliente"):
        if nome and endereco:
            clientes = carregar_json(ARQ_CLIENTES, [])
            clientes.append({"nome": nome, "endereco": endereco})
            salvar_json(ARQ_CLIENTES, clientes)
            st.success("Cliente adicionado!")
            st.rerun()
        else:
            st.warning("Preencha os dois campos.")

    clientes = carregar_json(ARQ_CLIENTES, [])
    st.subheader("📁 Lista de Clientes")
    for c in clientes:
        st.write(f"**{c['nome']}** — {c['endereco']}")

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

    clientes = carregar_json(ARQ_CLIENTES, [])
    if not clientes:
        st.info("Cadastre clientes antes de gerar a rota.")
        return

    selecionados = st.multiselect("Selecione os clientes com pedido:", [f"{c['nome']} – {c['endereco']}" for c in clientes])
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
            c = next(c for c in clientes if f"{c['nome']} – {c['endereco']}" == s)
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
                google_maps_url = f"https://www.google.com/maps/dir/" + "/".join(
                    [f"{coord[1]},{coord[0]}" for coord in coordenadas]
                )
                waze_url = f"https://waze.com/ul?ll={coordenadas[-1][1]},{coordenadas[-1][0]}&navigate=yes"

                st.markdown(f"**🗺️ Google Maps:** [Abrir Rota]({google_maps_url})", unsafe_allow_html=True)
                st.markdown(f"**🚗 Waze (último destino):** [Abrir Rota]({waze_url})", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Erro ao gerar rota: {e}")

# ======== CRIAR PEDIDOS =========
def aba_pedidos():
    st.header("🧾 Criar pedidos da semana")

    # Definir intervalo da semana
    if "data_inicio" not in st.session_state:
        st.session_state["data_inicio"] = date.today()
    if "data_fim" not in st.session_state:
        st.session_state["data_fim"] = date.today()

    # Input com valores persistentes
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Início da Semana", value=st.session_state["data_inicio"], format="DD/MM/YYYY")
        st.session_state["data_inicio"] = data_inicio
    with col2:
        data_fim = st.date_input("Fim da Semana", value=st.session_state["data_fim"], format="DD/MM/YYYY")
        st.session_state["data_fim"] = data_fim

    nome_aba = f"{data_inicio.strftime('%d-%m')} a {data_fim.strftime('%d-%m')}"

    # Valor base da cartela
    valor_base = st.number_input("💵 Valor Base da Cartela (R$)", min_value=0.0, format="%.2f")

    clientes = carregar_json(ARQ_CLIENTES, [])
    nomes_clientes = [c["nome"] for c in clientes]

    if not nomes_clientes:
        st.info("Cadastre clientes antes de registrar pedidos.")
        return

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

        nome_arquivo = "pedidos.xlsx"
        if os.path.exists(nome_arquivo):
            xls = pd.read_excel(nome_arquivo, sheet_name=None)
        else:
            xls = {}

        if nome_aba in xls:
            df_existente = xls[nome_aba]
            df_novo = pd.concat([df_existente, pd.DataFrame([novo_pedido])], ignore_index=True)
        else:
            df_novo = pd.DataFrame([novo_pedido])

        with pd.ExcelWriter(nome_arquivo, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            for aba_existente, df in xls.items():
                if aba_existente != "Sheet":  # evita sobrescrever aba default do Excel
                    df.to_excel(writer, sheet_name=aba_existente, index=False)
            df_novo.to_excel(writer, sheet_name=nome_aba, index=False)


        st.success("✅ Pedido salvo com sucesso!")


# ======== VISUALIZAR PEDIDOS =========
def aba_visualizar_pedidos():
    st.header("📂 Visualizar Pedidos Salvos")

    nome_arquivo = st.text_input("📄 Nome do arquivo (ex: pedidos.xlsx)")

    if nome_arquivo:
        if not os.path.exists(nome_arquivo):
            st.error("Arquivo não encontrado.")
            return

        try:
            planilhas = pd.read_excel(nome_arquivo, sheet_name=None)
            abas = list(planilhas.keys())

            aba_selecionada = st.selectbox("Selecione o intervalo da semana:", abas)

            df = planilhas[aba_selecionada]
            st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao carregar o arquivo: {e}")

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
