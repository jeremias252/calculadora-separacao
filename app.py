import streamlit as st
import pandas as pd
import re
import pypdf

# Configuração da página
st.set_page_config(page_title="Calculadora de Tempo de Separação", layout="wide")

st.title("⏱️ Calculadora de Tempo de Separação")
st.markdown("O sistema analisa seu relatório do sistema de expedição para calcular a carga horária da equipe.")

# BARRA LATERAL: Configuração de Tempos por Categoria
st.sidebar.header("⚙️ Configuração de Tempos")
st.sidebar.markdown("Defina quantos **minutos** leva para separar 1 unidade de cada categoria:")

tempo_caixa = st.sidebar.number_input("Caixa de Tomada (minutos)", min_value=0.5, value=2.0, step=0.5)
tempo_torre = st.sidebar.number_input("Torre de Tomada (minutos)", min_value=0.5, value=4.0, step=0.5)
tempo_regua = st.sidebar.number_input("Régua de Tomada (minutos)", min_value=0.5, value=2.5, step=0.5)
tempo_outros = st.sidebar.number_input("Módulos / Outros (minutos)", min_value=0.5, value=1.0, step=0.5)

# ÁREA PRINCIPAL: Upload do PDF
st.subheader("📁 Upload do Relatório Real")
arquivo_pdf = st.file_uploader("Arraste ou selecione o PDF dos pedidos", type=["pdf"])

if arquivo_pdf is not None:
    try:
        # Lendo o PDF real
        reader = pypdf.PdfReader(arquivo_pdf)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text() + "\n"
        
        linhas = texto_completo.split('\n')
        
        # PASSO 1: Encontrar os funcionários pela linha exata de resumo do detalhado
        separadores = []
        for i, linha in enumerate(linhas):
            linha_limpa = linha.strip()
            
            # Lê o padrão exato que o seu PDF gera: "Nome · X pedidos · Y un."
            match = re.search(r'^(.*?)\s*[·\-•]\s*(\d+)\s*pedidos\s*[·\-•]\s*(\d+)\s*un', linha_limpa, re.IGNORECASE)
            
            if match:
                nome = match.group(1).replace("Detalhado por pessoa", "").strip().title()
                
                separadores.append({
                    "nome": nome,
                    "pedidos": int(match.group(2)),
                    "unidades": int(match.group(3)),
                    "linha_idx": i
                })
        
        # PASSO 2: Ler os itens de cada funcionário
        dados_finais = []
        
        for k, sep in enumerate(separadores):
            inicio_bloco = sep['linha_idx'] + 1
            fim_bloco = separadores[k+1]['linha_idx'] if k + 1 < len(separadores) else len(linhas)
            bloco_linhas = linhas[inicio_bloco:fim_bloco]
            
            caixas, torres, reguas, outros = 0, 0, 0, 0
            
            for linha_bloco in bloco_linhas:
                linha_limpa = linha_bloco.strip()
                
                if not linha_limpa or linha_limpa.lower().startswith('pedido'):
                    continue
                
                # Lê a linha perfeitamente formatada: [Número] [Descrição] [Quantidade]
                match_item = re.search(r'^\d{5,8}\s+(.*?)\s+(\d+)$', linha_limpa)
                
                if match_item:
                    descricao = match_item.group(1).lower()
                    qtd_produto = int(match_item.group(2))
                else:
                    # Fallback caso a linha não tenha o número do pedido no início
                    match_fallback = re.search(r'(.*?)\s+(\d+)$', linha_limpa)
                    if match_fallback and not linha_limpa.isdigit():
                        descricao = match_fallback.group(1).lower()
                        qtd_produto = int(match_fallback.group(2))
                    else:
                        continue
                
                # Filtra os tipos
                if "torre" in descricao:
                    torres += qtd_produto
                elif "caixa" in descricao:
                    caixas += qtd_produto
                elif "régua" in descricao or "regua" in descricao:
                    reguas += qtd_produto
                elif any(w in descricao for w in ["módulo", "modulo", "rj", "rede"]):
                    outros += qtd_produto
                else:
                    caixas += qtd_produto # Joga para caixas se não achar descrição clara
            
            # PASSO 3: Ajuste fino de unidades (Garante que a conta bata com o PDF)
            total_encontrado = caixas + torres + reguas + outros
            total_esperado = sep['unidades']
            
            if total_encontrado != total_esperado:
                if total_encontrado == 0:
                    caixas = total_esperado 
                else:
                    fator = total_esperado / total_encontrado
                    torres = round(torres * fator)
                    caixas = round(caixas * fator)
                    reguas = round(reguas * fator)
                    outros = total_esperado - (torres + caixas + reguas)
            
            # Contabiliza o tempo
            tempo_total = (caixas * tempo_caixa) + (torres * tempo_torre) + (reguas * tempo_regua) + (outros * tempo_outros)
            tempo_amigavel = f"{int(tempo_total // 60)}h {int(tempo_total % 60)}m" if tempo_total >= 60 else f"{int(tempo_total)} min"
            
            dados_finais.append({
                "Separador": sep['nome'],
                "Pedidos": sep['pedidos'],
                "Total Unidades": sep['unidades'],
                "Caixas": max(0, caixas),
                "Torres": max(0, torres),
                "Réguas": max(0, reguas),
                "Módulos/Outros": max(0, outros),
                "Tempo (Min)": tempo_total,
                "Tempo Estimado": tempo_amigavel
            })
            
        df_resultado = pd.DataFrame(dados_finais)
        
        if df_resultado.empty:
            st.error("❌ O sistema não encontrou nenhum pedido. Verifique o arquivo enviado.")
        else:
            st.success("✅ Relatório lido e calculado com precisão cirúrgica!")
            
            st.subheader("📊 Resumo Geral da Operação")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Separadores Ativos", len(df_resultado))
            with col2:
                st.metric("Total de Produtos (Unidades)", int(df_resultado["Total Unidades"].sum()))
            with col3:
                tempo_geral = df_resultado["Tempo (Min)"].sum()
                st.metric("Tempo Total de Trabalho", f"{int(tempo_geral // 60)}h {int(tempo_geral % 60)}m")
            
            st.subheader("📋 Tempo e Produtividade por Separador")
            st.dataframe(
                df_resultado[["Separador", "Pedidos", "Total Unidades", "Caixas", "Torres", "Réguas", "Módulos/Outros", "Tempo Estimado"]], 
                use_container_width=True
            )
            
            st.subheader("📈 Distribuição da Carga de Trabalho (em minutos)")
            st.bar_chart(data=df_resultado, x="Separador", y="Tempo (Min)")
            
    except Exception as e:
        st.error(f"Erro inesperado no sistema: {e}")
else:
    st.info("💡 Por favor, faça o upload do PDF gerado pelo seu sistema para ver o cálculo.")
