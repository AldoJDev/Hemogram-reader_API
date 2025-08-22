import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional, Callable, Union
import pandas as pd
import fitz  # PyMuPDF
from dotenv import load_dotenv
from supabase import create_client, Client

PARAM_MAP: Dict[str, str] = {
    "colesterol hdl": "Colesterol HDL",
    "hdl": "Colesterol HDL",
    "triglicerideos": "Triglicerídeos",
    "triglicerides": "Triglicerídeos",
    "colesterol total": "Colesterol Total",
    "vitamina d3": "Vitamina D3",
    "vitamina d": "Vitamina D3",
    "vitamina d 25 hidroxi": "Vitamina D3",
    "sodio": "Sódio",
    "glicose": "Glicose",
    "potassio": "Potássio",
    "ferritina": "Ferritina",
    "hemacias": "Hemácias",
    "eritrocitos": "Hemácias",
    "hemoglobinas": "Hemoglobinas",
    "hemoglobina": "Hemoglobinas",
    "hematocritos": "Hematócritos",
    "hematocrito": "Hematócritos",
    "hcm": "HCM",
    "chcm": "CHCM",
    "vcm": "VCM",
    "ureia": "Ureia",
    "creatinina": "Creatinina",
    "colesterol ldl": "Colesterol LDL",
    "ldl": "Colesterol LDL",
    "tgp (alt)": "TGP (ALT)",
    "tgp": "TGP (ALT)",
    "alt": "TGP (ALT)",
    "transaminase piruvica": "TGP (ALT)",
    "rdw": "RDW",
    "vitamina b12": "Vitamina B12"
}

# Tolerância vertical em pixels para agrupar palavras na mesma linha.
Y_TOLERANCE: int = 5

# Mapa para normalização de caracteres, removendo acentos e símbolos.
TEXT_NORMALIZATION_MAP: Dict[str, str] = {
    'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'é': 'e', 'ê': 'e', 'í': 'i',
    'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c', ':': '', '(': '', ')': '',
    'ø': 'o', 'ü': 'u', 'û': 'u'
}

@dataclass(frozen=True)
class ExtractedMetric:
    name: str
    value: Union[float, int]

LineWords = List[Tuple[float, float, float, float, str, int, int, int]]
GroupedLines = Dict[float, LineWords]
ParserFunction = Callable[[str, List[str]], List[ExtractedMetric]]

def normalize_text(text: str) -> str:
    text_lower = text.lower()
    for char, replacement in TEXT_NORMALIZATION_MAP.items():
        text_lower = text_lower.replace(char, replacement)
    return text_lower.strip()

def is_numeric_value(s: str) -> bool:
    return bool(re.match(r'^[\d.,x\s]+$', s.strip()))

def clean_and_convert_to_float(s: str) -> Optional[float]:
    """
    Limpa e converte uma string para float, lidando com diferentes formatos
    numéricos (e.g., '1,23', '1.234,56', '10 x 10^3').
    """
    try:
        s_cleaned = s.strip().replace(' ', '')
        if 'x' in s_cleaned.lower():
            s_cleaned = s_cleaned.split('x')[0].strip()
        
        if ',' in s_cleaned and '.' in s_cleaned:
            s_cleaned = s_cleaned.replace('.', '').replace(',', '.')
        elif ',' in s_cleaned:
            parts = s_cleaned.split(',')
            # Trata casos como '3,5' (decimal) vs '1,234' (milhar).
            if len(parts) == 2 and len(parts[1]) <= 2:
                s_cleaned = s_cleaned.replace(',', '.')
            else:
                s_cleaned = s_cleaned.replace(',', '')
        
        if s_cleaned.endswith('.'):
            s_cleaned = s_cleaned[:-1]
        return float(s_cleaned)
    except (ValueError, TypeError):
        return None

def extract_numbers_from_text(text: str, is_result_line: bool = False) -> List[float]:
    if is_result_line or "resultado" in text.lower():
        pattern = r'resultado[:\s]*([\d.,]+)'
        match = re.search(pattern, text.lower())
        if match:
            num = clean_and_convert_to_float(match.group(1))
            if num is not None:
                return [num]

    # Expressão regular para extrair números que não estão adjacentes a letras.
    generic_pattern = r'(?<![A-Za-z])\b[\d]+(?:[.,][\d]+)?\b(?![A-Za-z])'
    matches = re.findall(generic_pattern, text)
    
    if not matches and is_result_line:
        simple_pattern = r'[\d]+(?:[.,][\d]+)?'
        matches = re.findall(simple_pattern, text)

    numbers = [clean_and_convert_to_float(match) for match in matches]
    return [num for num in numbers if num is not None]

def parse_generic_metric(std_name: str, line_numbers: List[float]) -> List[ExtractedMetric]:
    if not line_numbers:
        return []
    return [ExtractedMetric(name=std_name, value=line_numbers[0])]

def group_words_into_lines(page: fitz.Page) -> GroupedLines:
    """
    Agrupa palavras extraídas pelo PyMuPDF em linhas com base em sua coordenada Y.
    """
    lines: GroupedLines = defaultdict(list)
    words = page.get_text("words")
    
    for word in words:
        y0 = word[1]
        found_line = False
        for y_key in list(lines.keys()):
            if abs(y_key - y0) < Y_TOLERANCE:
                lines[y_key].append(word)
                found_line = True
                break
        if not found_line:
            lines[y0].append(word)
    
    return lines

def find_metric_in_line(line_text: str, normalized_line: str) -> Optional[str]:
    """
    Busca por um nome de métrica na linha, priorizando os termos mais longos
    para evitar correspondências parciais (ex: 'ldl' em 'colesterol ldl').
    """
    sorted_keys = sorted(PARAM_MAP.keys(), key=len, reverse=True)
    
    for search_term in sorted_keys:
        if search_term in normalized_line:
            return PARAM_MAP[search_term]
    return None

def find_value_in_structured_layout(
    all_lines: GroupedLines, current_y: float, metric_x_end: float
) -> Optional[float]:
    """
    Busca o valor de uma métrica nas linhas subsequentes, comum em layouts
    onde o resultado está abaixo do nome do exame.
    """
    y_keys = sorted(all_lines.keys())
    try:
        current_idx = y_keys.index(current_y)
    except ValueError:
        return None

    search_range = min(3, len(y_keys) - current_idx - 1)

    for i in range(1, search_range + 1):
        next_y = y_keys[current_idx + i]
        line_words = sorted(all_lines[next_y], key=lambda w: w[0])
        line_text = " ".join(w[4] for w in line_words)
        
        if "resultado" in line_text.lower():
            numbers = extract_numbers_from_text(line_text, is_result_line=True)
            if numbers:
                return numbers[0]

        for word in line_words:
            word_x_start = word[0]
            # Considera que o valor está alinhado ou à direita do nome da métrica.
            if word_x_start > metric_x_end - 20: 
                num = clean_and_convert_to_float(word[4])
                if num is not None:
                    return num
    return None

def process_line(line_words: LineWords, processed_metrics: Set[str], all_lines: GroupedLines, current_y: float) -> List[ExtractedMetric]:
    line_text = " ".join([w[4] for w in line_words])
    normalized_line_text = normalize_text(line_text)

    std_name = find_metric_in_line(line_text, normalized_line_text)
    if not std_name or std_name in processed_metrics:
        return []

    metric_pos = normalized_line_text.find(next(k for k, v in PARAM_MAP.items() if v == std_name))
    text_after_metric = line_text[metric_pos + len(std_name):]
    
    line_numbers = extract_numbers_from_text(text_after_metric)

    if not line_numbers:
        metric_word_info = line_words[-1]
        metric_x_end = metric_word_info[2]
        
        value = find_value_in_structured_layout(all_lines, current_y, metric_x_end)
        if value is not None:
            line_numbers = [value]

    if not line_numbers:
        return []

    final_value = line_numbers[0]
    # Filtro para valores absurdamente altos que podem ser erros de leitura.
    if final_value > 10000:
        print(f"Valor suspeito {final_value} para '{std_name}' foi ignorado.")
        return []

    return [ExtractedMetric(name=std_name, value=final_value)]

def extract_data_from_pdf(pdf_bytes: bytes) -> List[ExtractedMetric]:
    all_results: List[ExtractedMetric] = []
    processed_metrics: Set[str] = set()
    
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                lines = group_words_into_lines(page)
                
                for y_key in sorted(lines.keys()):
                    line_words = sorted(lines[y_key], key=lambda w: w[0])
                    found_metrics = process_line(line_words, processed_metrics, lines, y_key)
                    
                    if found_metrics:
                        all_results.extend(found_metrics)
                        for metric in found_metrics:
                            processed_metrics.add(metric.name)
    
    except Exception as e:
        print(f"Erro ao processar PDF: {e}")
        return []
    
    # Garante que cada métrica apareça apenas uma vez.
    unique_results = []
    seen_names = set()
    for result in all_results:
        if result.name not in seen_names:
            unique_results.append(result)
            seen_names.add(result.name)
    
    return unique_results

def create_results_dataframe(exam_results: List[ExtractedMetric], patient_id: str = "Paciente", exam_date: str = "Data não informada") -> pd.DataFrame:
    if not exam_results:
        return pd.DataFrame(columns=['Paciente', 'Data_Exame', 'Métrica', 'Valor', 'Unidade'])
    
    unit_map = {
        "Hemácias": "milhões/mm³", "Hemoglobinas": "g/dL", "Hematócritos": "%", "VCM": "fL", "HCM": "pg",
        "CHCM": "g/dL", "RDW": "%", "Colesterol Total": "mg/dL", "Colesterol HDL": "mg/dL",
        "Colesterol LDL": "mg/dL", "Triglicerídeos": "mg/dL", "Glicose": "mg/dL", "Ureia": "mg/dL",
        "Creatinina": "mg/dL", "TGP (ALT)": "U/L", "Ferritina": "ng/mL", "Vitamina D3": "ng/mL",
        "Vitamina B12": "pg/mL", "Sódio": "mEq/L", "Potássio": "mEq/L",
    }
    
    data = []
    for metric in exam_results:
        unit = unit_map.get(metric.name, "N/A")
        data.append({
            'Paciente': patient_id, 'Data_Exame': exam_date, 'Métrica': metric.name,
            'Valor': metric.value, 'Unidade': unit
        })
    
    df = pd.DataFrame(data)
    
    # Define uma ordem de exibição lógica para as métricas no DataFrame.
    metric_order = [
        "Hemácias", "Hemoglobinas", "Hematócritos", "VCM", "HCM", "CHCM", "RDW", "Glicose", "Ureia",
        "Creatinina", "Colesterol Total", "Colesterol HDL", "Colesterol LDL", "Triglicerídeos",
        "TGP (ALT)", "Ferritina", "Sódio", "Potássio", "Vitamina D3", "Vitamina B12"
    ]
    
    df['Métrica'] = pd.Categorical(df['Métrica'], categories=metric_order, ordered=True)
    df = df.sort_values('Métrica').reset_index(drop=True)
    
    return df

def display_results_summary(df: pd.DataFrame):
    if df.empty:
        print("Nenhum dado foi extraído do PDF.")
        return
    
    print("="*60)
    print(f"RESULTADOS EXTRAÍDOS - {df.iloc[0]['Paciente']}")
    print(f"Data do Exame: {df.iloc[0]['Data_Exame']}")
    print("="*60)

    for _, row in df.iterrows():
        print(f"{row['Métrica']:.<25} {row['Valor']:>8} {row['Unidade']}")
    
    print(f"\n📋 Total de métricas extraídas: {len(df)}")
    print("="*60)

def upload_to_supabase(df: pd.DataFrame, supabase_client: Client, user_id: str):
    if df.empty:
        print("DataFrame vazio. Nenhum dado para enviar ao Supabase.")
        return

    exam_date = df.iloc[0]['Data_Exame']

    try:
        # 1. Insere um novo registro de exame para o usuário.
        user_exam_insert = {"user_id": user_id, "exam_date": exam_date}
        user_exam_response = supabase_client.table("hf_user_exam").insert(user_exam_insert).execute()
        user_exam_id = user_exam_response.data[0]['id']
        print(f"Registro de exame inserido com sucesso. ID: {user_exam_id}")

        # 2. Busca os IDs das métricas existentes no banco de dados.
        metric_names = df['Métrica'].unique().tolist()
        metrics_response = supabase_client.table("hf_exam_metric").select("id, name").in_("name", metric_names).execute()
        if not metrics_response.data:
            print("Nenhuma das métricas foi encontrada na tabela 'hf_exam_metric'.")
            return
        metric_id_map = {metric['name']: metric['id'] for metric in metrics_response.data}
        print("IDs das métricas encontrados.")

        # 3. Prepara e insere os resultados dos exames.
        results_to_insert = []
        for _, row in df.iterrows():
            metric_name = row['Métrica']
            if metric_name in metric_id_map:
                results_to_insert.append({
                    "user_exam_id": user_exam_id,
                    "metric_id": metric_id_map[metric_name],
                    "value_numeric": row['Valor'],
                    "status": "completed"
                })
        
        if results_to_insert:
            print(f"Inserindo {len(results_to_insert)} resultados...")
            results_response = supabase_client.table("hf_user_exam_result").insert(results_to_insert).execute()
            if results_response.data:
                print("Todos os resultados foram inseridos com sucesso no Supabase!")
            else:
                print("Ocorreu um erro ao inserir os resultados.")

    except Exception as e:
        print(f"Ocorreu um erro durante a comunicação com o Supabase: {e}")

def process_exam_pdf(pdf_bytes: bytes, patient_id: str, exam_date: str) -> Optional[pd.DataFrame]:
    try:
        exam_results = extract_data_from_pdf(pdf_bytes)
        if not exam_results:
            print("Nenhuma métrica foi encontrada no documento.")
            return None
        
        df = create_results_dataframe(exam_results, patient_id, exam_date)
        if df.empty:
            print("Não foi possível criar o DataFrame com os resultados.")
            return None
            
        display_results_summary(df)
        
        load_dotenv()
        url = os.getenv("supabase_url")
        key = os.getenv("supabase_key")

        if not url or not key:
            print("Variáveis de ambiente do Supabase não configuradas. Pulando upload.")
            return df

        try:
            supabase: Client = create_client(url, key)
            upload_to_supabase(df, supabase, user_id=patient_id)
        except Exception as e:
            print(f"Falha ao conectar ou enviar dados para o Supabase: {e}")

        return df
        
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante o processamento: {str(e)}")
        return None