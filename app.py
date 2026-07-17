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
        
        # Encontra os separadores e seus totais usando o padrão do relatório: "Nome X pedidos Y un."
        padrao_separador = r"([A-ZÀ-ÿa-z\s]+?)\s+(\d+)\s+pedidos\s+(\d+)\s+un"
        matches_iter = list(re.finditer(padrao_separador, texto_completo, re.IGNORECASE))
        
        dados_finais = []
        
        for idx, match in enumerate(matches_iter):
            nome_cru = match.group(1)
            # Limpa sujeiras de cabeçalho do PDF
            nome = nome_cru.replace("Detalhado por pessoa", "").replace("Resumo por pessoa", "").strip().title()
            
            # Filtra linhas falsas ou cabeçalhos da tabela
            if "Pessoa" in nome or "Pedido" in nome or not nome:
                continue
                
            qtd_pedidos = int(match.group(2))
            total_unidades = int(match.group(3))
            
            # Isola o bloco de texto específico deste separador
            start = match.end()
            end = matches_iter[idx+1].start() if idx + 1 < len(matches_iter) else len(texto_completo)
            bloco_texto = texto_completo[start:end].lower()
            
            # Contagem inteligente por palavras-chave dentro do bloco do separador
            linhas = bloco_texto.split('\n')
            t_count, c_count, r_count, o_count = 0, 0, 0, 0
            
            for l_idx, linha in enumerate(linhas):
                linha = linha.strip()
                if not linha:
                    continue
                
                # Define a quantidade da linha (procura por número no fim ou na linha seguinte se quebrado)
                qtd_linha = 1
                parts = linha.split('|')
                if len(parts) >= 2 and parts[-1].strip().isdigit():
                    qtd_linha = int(parts[-1].strip())
                elif l_idx + 1 < len(linhas) and lines[l_idx+1].strip().isdigit():
                    qtd_linha = int(linhas[l_idx+1].strip())
                
                # Classifica por palavra-chave
                if "torre" in linha:
                    t_count += qtd_linha
                elif "caixa" in linha:
                    c_count += qtd_linha
                elif "régua" in linha or "regua" in linha:
                    r_count += qtd_linha
                elif "módulo" in linha or "modulo" in linha:
                    o_count += qtd_linha
            
            # Ajuste proporcional: Garante que a soma das categorias bata EXATAMENTE com o total do PDF
            total_detectado = t_count + c_count + r_count + o_count
            if total_detectado > 0 and total_detectado != total_unidades:
                fator = total_unidades / total_detectado
                t_count = round(t_count * fator)
                c_count = round(c_count * fator)
                r_count = round(r_count * fator)
                o_count = total_unidades - (t_count + c_count + r_count)
            elif total_detectado == 0:
                c_count = total_unidades # Fallback de segurança
                
            # Calcula o tempo total deste funcionário baseado nas regras da barra lateral
            tempo_total_minutos = (
                (c_count * tempo_caixa) + 
                (t_count * tempo_torre) + 
                (r_count * tempo_regua) + 
                (o_count * tempo_outros)
            )
            
            # Formata o tempo para exibição amigável (ex: 1h 20m)
            tempo_amigavel = f"{int(tempo_total_minutos // 60)}h {int(tempo_total_minutos % 60)}m" if tempo_total_minutos >= 60 else f"{int(tempo_total_minutos)} min"
            
            dados_finais.append({
                "Separador": nome,
                "Pedidos": qtd_pedidos,
                "Total Unidades": total_unidades,
                "Caixas": c_count,
                "Torres": t_count,
                "Réguas": r_count,
                "Módulos/Outros": o_count,
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
