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
        
        # Quebra o texto em linhas para uma varredura resiliente
        linhas = texto_completo.split("\n")
        secoes_separadores = []
        
        # Passo 1: Identificar as linhas de início de cada separador
        for i, linha in enumerate(linhas):
            match = re.search(r"(\d+)\s+pedidos\s+(\d+)\s+un", linha, re.IGNORECASE)
            if match:
                qtd_pedidos = int(match.group(1))
                total_unidades = int(match.group(2))
                
                # Descobre o nome do separador (na mesma linha ou na anterior)
                texto_antes = linha[:match.start()].strip()
                if len(texto_antes) > 3:
                    nome = texto_antes
                else:
                    # Busca nas linhas anteriores por um nome válido
                    nome = ""
                    for j in range(i-1, -1, -1):
                        linha_anterior = linhas[j].strip()
                        if linha_anterior and not any(w in linha_anterior.lower() for w in ["pedido", "item", "qtd", "|", "unidades"]):
                            linha_anterior = linha_anterior.replace("Detalhado por pessoa", "").replace("Resumo por pessoa", "").strip()
                            if linha_anterior:
                                nome = linha_anterior
                                break
                
                # Limpeza final do nome
                nome = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', nome).strip().title()
                if not nome:
                    nome = f"Separador Desconhecido ({qtd_pedidos} ped)"
                    
                secoes_separadores.append({
                    "nome": nome,
                    "pedidos": qtd_pedidos,
                    "unidades": total_unidades,
                    "linha_inicial": i
                })
        
        dados_finais = []
        
        # Passo 2: Processar os itens de cada secao encontrada
        for idx, sec in enumerate(secoes_separadores):
            start_l = sec["linha_inicial"] + 1
            end_l = secoes_separadores[idx+1]["linha_inicial"] if idx + 1 < len(secoes_separadores) else len(linhas)
            
            bloco_linhas = linhas[start_l:end_l]
            t_count, c_count, r_count, o_count = 0, 0, 0, 0
            
            for l_idx, l in enumerate(bloco_linhas):
                l_lower = l.lower().strip()
                if not l_lower or any(w in l_lower for w in ["pedido", "item", "qtd"]):
                    continue
                
                # Ignora linhas que são apenas números isolados (já capturadas pelo lookahead anterior)
                if l_lower.isdigit():
                    continue
                
                # Tenta capturar a quantidade do produto na linha atual ou na próxima
                qtd_linha = 0
                parts = [p.strip() for p in l.split("|")]
                
                if len(parts) >= 2 and parts[-1].isdigit():
                    qtd_linha = int(parts[-1])
                else:
                    match_fim_num = re.search(r"\b(\d+)$", l.strip())
                    if match_fim_num:
                        qtd_linha = int(match_fim_num.group(1))
                    elif l_idx + 1 < len(bloco_linhas) and bloco_linhas[l_idx+1].strip().isdigit():
                        qtd_linha = int(bloco_linhas[l_idx+1].strip())
                
                if qtd_linha == 0:
                    qtd_linha = 1 # Fallback padrão
                
                # Classificação por palavra-chave do produto
                if "torre" in l_lower:
                    t_count += qtd_linha
                elif "caixa" in l_lower:
                    c_count += qtd_linha
                elif "régua" in l_lower or "regua" in l_lower:
                    r_count += qtd_linha
                elif any(w in l_lower for w in ["módulo", "modulo", "rj-45", "rede"]):
                    o_count += qtd_linha
            
            # Ajuste Fino: Força a soma das categorias a bater com o total declarado no PDF
            total_unidades = sec["unidades"]
            total_detectado = t_count + c_count + r_count + o_count
            if total_detectado > 0 and total_detectado != total_unidades:
                fator = total_unidades / total_detectado
                t_count = round(t_count * fator)
                c_count = round(c_count * fator)
                r_count = round(r_count * fator)
                o_count = total_unidades - (t_count + c_count + r_count)
            elif total_detectado == 0:
                c_count = total_unidades
            
            # Cálculo de tempo
            tempo_total_minutos = (c_count * tempo_caixa) + (t_count * tempo_torre) + (r_count * tempo_regua) + (o_count * tempo_outros)
            tempo_amigavel = f"{int(tempo_total_minutos // 60)}h {int(tempo_total_minutos % 60)}m" if tempo_total_minutos >= 60 else f"{int(tempo_total_minutos)} min"
            
            dados_finais.append({
                "Separador": sec["nome"],
                "Pedidos": sec["pedidos"],
                "Total Unidades": total_unidades,
                "Caixas": c_count,
                "Torres": t_count,
                "Réguas": r_count,
                "Tempo_Minutos": tempo_total_minutos,
                "Tempo Estimado": tempo_amigavel
            })
            
        df_resultado = pd.DataFrame(dados_finais)
        
        if not df_resultado.empty:
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
