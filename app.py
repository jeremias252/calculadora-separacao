import streamlit as st
import pandas as pd
import re
import pypdf

# Configuração da página
st.set_page_config(page_title="Calculadora de Tempo de Separação", layout="wide")

st.title("⏱️ Calculadora de Tempo de Separação (Versão Ultra-Resiliente)")
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
        
        # ABA DE DEPURAÇÃO (Ajuda a descobrir se o PDF veio como imagem ou texto bagunçado)
        with st.expander("🔍 Ver texto extraído do PDF (Clique para expandir/ocultar)"):
            if texto_completo.strip():
                st.text(texto_completo[:2000] + "\n\n[... Mostrando os primeiros 2000 caracteres ...]")
            else:
                st.error("❌ O texto extraído está COMPLETAMENTE VAZIO! Este PDF foi escaneado como imagem ou foto? O sistema precisa de PDFs gerados diretamente pelo sistema com texto selecionável.")

        if not texto_completo.strip():
            st.stop()

        # NORMALIZAÇÃO DO TEXTO: Junta tudo em uma linha contínua, eliminando quebras de linha invisíveis
        texto_sub = re.sub(r'\s+', ' ', texto_completo)
        
        # Padrão flexível para encontrar os blocos de cada pessoa: "Nome X pedidos Y un"
        padrao = r"([A-Za-zÀ-ÿ\s\.]+?)\s*(\d+)\s*pedidos\s*(\d+)\s*un"
        matches = list(re.finditer(padrao, texto_sub, re.IGNORECASE))
        
        dados_finais = []
        
        for idx, match in enumerate(matches):
            nome_cru = match.group(1).strip()
            
            # Limpeza do nome tirando restos de cabeçalhos das tabelas
            nome = nome_cru
            for termo in ["detalhado por pessoa", "resumo por pessoa", "unidades", "pedidos", "pessoa", "montagem", "conferência"]:
                if termo in nome.lower():
                    partes = re.split(termo, nome, flags=re.IGNORECASE)
                    nome = partes[-1].strip()
            
            # Mantém apenas letras no nome
            nome = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', nome).strip().title()
            
            if not nome or len(nome) < 3 or nome.lower() in ["item", "qtd", "pedido"]:
                continue
                
            qtd_pedidos = int(match.group(2))
            total_unidades = int(match.group(3))
            
            # Isola os produtos pertencentes a este funcionário específico
            start_pos = match.end()
            end_pos = matches[idx+1].start() if idx + 1 < len(matches) else len(texto_sub)
            bloco_texto = texto_sub[start_pos:end_pos].lower()
            
            # Divide os itens usando o número do pedido (5 a 7 dígitos) como separador lógico
            itens = re.split(r'\b\d{5,7}\b', bloco_texto)
            
            t_count, c_count, r_count, o_count = 0, 0, 0, 0
            
            for item in itens:
                if not item.strip():
                    continue
                
                # Captura a quantidade no fim da descrição do item
                match_qtd = re.search(r'(?:\|\s*|\s+)(\d+)\s*$', item.strip())
                if match_qtd:
                    qtd_linha = int(match_qtd.group(1))
                else:
                    qtd_linha = 1
                
                # Filtra por palavras-chave
                if "torre" in item:
                    t_count += qtd_linha
                elif "caixa" in item:
                    c_count += qtd_linha
                elif "régua" in item or "regua" in item:
                    r_count += qtd_linha
                elif any(w in item for w in ["módulo", "modulo", "rj-45", "rede"]):
                    o_count += qtd_linha
            
            # Força o ajuste matemático para bater com o cabeçalho do PDF
            total_detectado = t_count + c_count + r_count + o_count
            if total_detectado != total_unidades:
                if total_detectado == 0:
                    c_count = total_unidades  
                else:
                    fator = total_unidades / total_detectado
                    t_count = round(t_count * fator)
                    c_count = round(c_count * fator)
                    r_count = round(r_count * fator)
                    o_count = total_unidades - (t_count + c_count + r_count)
            
            # Contabilidade dos tempos
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
            st.warning("⚠️ Não encontramos dados de separadores no formato esperado dentro do PDF. Por favor, clique na barra de ferramentas 'Ver texto extraído do PDF' logo acima para ver o que há de errado.")
            
    except Exception as e:
        st.error(f"Erro ao ler o arquivo PDF: {e}")
else:
    st.info("💡 Por favor, faça o upload do PDF gerado pelo seu sistema para ver o cálculo.")
