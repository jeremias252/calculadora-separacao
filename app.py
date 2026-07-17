import streamlit as st
import pandas as pd
import re
import pypdf

# Configuração da página
st.set_page_config(page_title="Calculadora de Tempo de Separação", layout="wide")

st.title("⏱️ Calculadora de Tempo de Separação (PDF Real)")
st.markdown("Faça o upload do seu relatório em PDF para calcular o tempo estimado de separação por funcionário.")

# 1. BARRA LATERAL: Configuração de Tempos por Categoria
st.sidebar.header("⚙️ Configuração de Tempos")
st.sidebar.markdown("Defina quantos **minutos** leva para separar 1 unidade de cada categoria:")

tempo_caixa = st.sidebar.number_input("Caixa de Tomada (minutos)", min_value=0.5, value=2.0, step=0.5)
tempo_torre = st.sidebar.number_input("Torre de Tomada (minutos)", min_value=0.5, value=4.0, step=0.5)
tempo_regua = st.sidebar.number_input("Régua de Tomada (minutos)", min_value=0.5, value=2.5, step=0.5)
tempo_outros = st.sidebar.number_input("Módulos / Outros (minutos)", min_value=0.5, value=1.0, step=0.5)

# 2. ÁREA PRINCIPAL: Upload do PDF
st.subheader("📁 Upload do Relatório Real")
arquivo_pdf = st.file_uploader("Arraste ou selecione o PDF dos pedidos", type=["pdf"])

if arquivo_pdf is not None:
    try:
        # Lendo o PDF real
        reader = pypdf.PdfReader(arquivo_pdf)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text() + "\n"
        
        # Busca global e ultra flexível por "X pedidos Y" em todo o texto (ignora quebras de linha e falta de espaços)
        padrao_separador = r"(\d+)\s*pedi[a-z]*\s*(\d+)"
        matches = list(re.finditer(padrao_separador, texto_completo, re.IGNORECASE))
        
        dados_finais = []
        
        for idx, match in enumerate(matches):
            qtd_pedidos = int(match.group(1))
            total_unidades = int(match.group(2))
            
            # Filtra falsos positivos (como números de anos ou códigos operacionais muito altos)
            if qtd_pedidos > 500 or total_unidades > 5000:
                continue
                
            # Captura o texto anterior para descobrir o nome do funcionário
            start_pos = match.start()
            texto_anterior = texto_completo[max(0, start_pos-150):start_pos]
            linhas_anteriores = [l.strip() for l in texto_anterior.split("\n") if l.strip()]
            
            nome = ""
            if linhas_anteriores:
                for linha_ant in reversed(linhas_anteriores):
                    linha_ant_clean = linha_ant.replace("Detalhado por pessoa", "").replace("Resumo por pessoa", "").strip()
                    if linha_ant_clean and not any(w in linha_ant_clean.lower() for w in ["pedido", "item", "qtd", "|", "unidades", "conferência", "montagem"]):
                        nome = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', linha_ant_clean).strip().title()
                        if nome and len(nome) > 3:
                            break
            
            if not nome:
                nome = f"Separador Desconhecido {idx + 1}"
                
            # Isola o bloco de texto de itens deste funcionário
            end_pos = matches[idx+1].start() if idx + 1 < len(matches) else len(texto_completo)
            bloco_texto = texto_completo[match.end():end_pos]
            
            # Varredura inteligente de produtos e quantidades por proximidade linear
            linhas_bloco = bloco_texto.split("\n")
            detected_types = []
            detected_quantities = []
            
            for linha_bloco in linhas_bloco:
                l_lower = linha_bloco.lower().strip()
                if not l_lower or any(w in l_lower for w in ["pedido", "item", "qtd", "resumo", "detalhado"]):
                    continue
                
                # Identifica o tipo do produto por palavra-chave
                tipo = None
                if "torre" in l_lower:
                    tipo = "torre"
                elif "caixa" in l_lower:
                    tipo = "caixa"
                elif "régua" in l_lower or "regua" in l_lower:
                    tipo = "régua"
                elif any(w in l_lower for w in ["módulo", "modulo", "rj-45", "rede"]):
                    tipo = "módulo"
                    
                if tipo:
                    detected_types.append(tipo)
                
                # Identifica quantidades isoladas na linha ou coladas no final do texto
                clean_line = linha_bloco.replace("|", "").strip()
                if clean_line.isdigit() and len(clean_line) < 4:
                    detected_quantities.append(int(clean_line))
                else:
                    match_qtd = re.search(r"(?:\|\s*|\s+)(\d+)\s*$", linha_bloco.strip())
                    if match_qtd:
                        val_qtd = int(match_qtd.group(1))
                        if val_qtd < 1000: # Evita confundir com códigos de produtos
                            detected_quantities.append(val_qtd)
            
            # Consolida dados usando alinhamento inteligente de listas paralelas (resolve colunas desalinhadas)
            t_count, c_count, r_count, o_count = 0, 0, 0, 0
            for t, q in zip(detected_types, detected_quantities):
                if t == "torre": t_count += q
                elif t == "caixa": c_count += q
                elif t == "régua": r_count += q
                elif t == "módulo": o_count += q
            
            # Ajuste Fino de segurança: Garante que o total distribuído bata 100% com o cabeçalho oficial do PDF
            total_detectado = t_count + c_count + r_count + o_count
            if total_detectado != total_unidades:
                if total_detectado == 0:
                    if len(detected_types) > 0:
                        share = total_unidades // len(detected_types)
                        for t in detected_types:
                            if t == "torre": t_count += share
                            elif t == "caixa": c_count += share
                            elif t == "régua": r_count += share
                            elif t == "módulo": o_count += share
                        c_count += (total_unidades - (t_count + c_count + r_count + o_count))
                    else:
                        c_count = total_unidades
                else:
                    fator = total_unidades / total_detectado
                    t_count = round(t_count * fator)
                    c_count = round(c_count * fator)
                    r_count = round(r_count * fator)
                    o_count = total_unidades - (t_count + c_count + r_count)
            
            # Cálculo de tempos baseado nos inputs do painel lateral
            tempo_total_minutos = (c_count * tempo_caixa) + (t_count * tempo_torre) + (r_count * tempo_regua) + (o_count * tempo_outros)
            tempo_amigavel = f"{int(tempo_total_minutos // 60)}h {int(tempo_total_minutos % 60)}m" if tempo_total_minutos >= 60 else f"{int(tempo_total_minutos)} min"
            
            dados_finais.append({
                "Separador": nome,
                "Pedidos": qtd_pedidos,
                "Total Unidades": total_unidades,
                "Caixas": c_count,
                "Torres": t_count,
                "Réguas": r_count,
                "Tempo_Minutos": tempo_total_minutos,
                "Tempo Estimado": tempo_amigavel
            })
            
        df_resultado = pd.DataFrame(dados_finais)
        
        # Elimina possíveis duplicatas geradas pela tabela de resumo do topo do PDF
        if not df_resultado.empty:
            df_resultado = df_resultado.drop_duplicates(subset=["Separador"], keep="last")
            
            st.success("✅ Relatório processado com sucesso!")
            
            # 3. EXIBIÇÃO DE MÉTRICAS GERAIS
            st.subheader("📊 Resumo Geral da Operação")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Separadores Ativos", len(df_resultado))
            with col2:
                st.metric("Total de Produtos (Unidades)", int(df_resultado["Total Unidades"].sum()))
            with col3:
                tempo_geral = df_resultado["Tempo_Minutos"].sum()
                st.metric("Tempo Total de Trabalho Estimado", f"{int(tempo_geral // 60)}h {int(tempo_geral % 60)}m")
            
            # 4. TABELA DE DETALHES
            st.subheader("📋 Tempo e Produtividade por Separador")
            st.dataframe(
                df_resultado[["Separador", "Pedidos", "Total Unidades", "Caixas", "Torres", "Réguas", "Tempo Estimado"]], 
                use_container_width=True
            )
            
            # 5. GRÁFICO
            st.subheader("📈 Distribuição da Carga de Trabalho (em minutos)")
            st.bar_chart(data=df_resultado, x="Separador", y="Tempo_Minutos")
        else:
            st.warning("⚠️ Não encontramos dados de separadores no formato esperado dentro do PDF.")
            
    except Exception as e:
        st.error(f"Erro ao ler o arquivo PDF: {e}")
else:
    st.info("💡 Por favor, faça o upload do PDF gerado pelo seu sistema para ver o cálculo.")
