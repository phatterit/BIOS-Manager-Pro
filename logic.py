import os
import json
import urllib.parse
import re
from datetime import datetime
import pandas as pd
from packaging import version
from models import db, BiosReference
from sqlalchemy import func

# --- NARZĘDZIA POMOCNICZE ---

def normalize_name(name):
    if not name: return ""
    return str(name).strip().lower()

def clean_version_string(v_str):
    """
    Inteligentnie wyciąga wersję BIOS z ciągu znaków.
    Obsługuje: "1.20", "Ver 1.20 (A03)", "A14", "N1CET90W (1.58 )"
    """
    if not v_str or pd.isna(v_str): return "0.0"
    v_str = str(v_str).strip()
    
    # Priorytet 1: Szukamy formatu X.Y.Z (np. 1.2.3 lub 1.20)
    match_standard = re.search(r'(\d+(?:\.\d+)+)', v_str)
    if match_standard:
        return match_standard.group(1)
    
    # Priorytet 2: Stare Delle (np. A14 -> 14 lub A03 -> 3)
    # Wyciągamy pierwszą liczbę, jeśli string jest krótki i zaczyna się od A
    if v_str.upper().startswith('A') and len(v_str) < 5:
        match_simple = re.search(r'\d+', v_str)
        if match_simple:
            return match_simple.group(0)

    # Priorytet 3: Jakakolwiek sekwencja cyfr
    match_any = re.search(r'\d+', v_str)
    if match_any:
        return match_any.group(0)
        
    return "0.0"

def compare_versions(pc_ver, db_ver):
    try:
        v1 = clean_version_string(pc_ver)
        v2 = clean_version_string(db_ver)
        parsed_pc = version.parse(v1)
        parsed_db = version.parse(v2)
        if parsed_pc == parsed_db: return 0
        elif parsed_pc > parsed_db: return 1
        else: return -1
    except:
        if str(pc_ver) == str(db_ver): return 0
        return 1 if str(pc_ver) > str(db_ver) else -1

# --- OBSŁUGA PLIKÓW JSON (BRAKOWAŁO TEGO!) ---

def load_json_db(filepath):
    if not os.path.exists(filepath): return {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        try: return json.load(f)
        except: return {}

def save_json_db(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- OBSŁUGA BAZY DANYCH ---

def get_db_reference(model_raw):
    normalized_input = normalize_name(model_raw)
    ref = BiosReference.query.filter(func.lower(BiosReference.model_name) == normalized_input).first()
    if ref: return ref
    for prefix in ["dell ", "lenovo ", "hp "]:
        if prefix not in normalized_input:
            candidate = prefix + normalized_input
            ref = BiosReference.query.filter(func.lower(BiosReference.model_name) == candidate).first()
            if ref: return ref
    return None

def process_uploaded_file(filepath):
    rows = []
    stats = {
        'total': 0, 'ok': 0, 'outdated': 0, 'unknown': 0, 'newer': 0, 'compliance_rate': 0,
        'risk_icon': 'bi-emoji-expressionless', 'risk_color': 'secondary', 'risk_text': 'BRAK DANYCH',
        'outdated_pct': 0,
        'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'departments': [],
        'chart_dept_labels': "",
        'chart_dept_data': ""
    }
    
    departments_raw = {} 

    try:
        if filepath.endswith('.csv'):
            try: df = pd.read_csv(filepath, sep=',') 
            except: df = pd.read_csv(filepath, sep=';')
        else:
            df = pd.read_excel(filepath)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        cols_map = {}
        for c in df.columns:
            cl = c.lower()
            if 'model' in cl: cols_map['model'] = c
            elif 'ver' in cl or 'bios' in cl: cols_map['ver'] = c
            elif 'name' in cl or 'host' in cl or 'computer' in cl: cols_map['name'] = c
            elif 'tag' in cl or 'serial' in cl: cols_map['tag'] = c
            
        for _, row in df.iterrows():
            m_raw = str(row.get(cols_map.get('model'), 'Unknown')).strip()
            v_pc = str(row.get(cols_map.get('ver'), '0.0')).strip()
            comp = str(row.get(cols_map.get('name'), '---')).strip()
            tag = str(row.get(cols_map.get('tag'), '---')).strip()
            
            # Ekstrakcja oddziału
            if '-' in comp: dept_code = comp.split('-')[0].upper()
            else: dept_code = "INNE"
            
            if dept_code not in departments_raw:
                departments_raw[dept_code] = {'total': 0, 'ok': 0, 'outdated': 0, 'unknown': 0}

            res = {
                "computer_name": comp, "model": m_raw, "service_tag": tag, 
                "current": v_pc, "latest": "---", "status": "Nieznany", 
                "color": "secondary", "filter_cat": "unknown", "match_model": "---"
            }

            departments_raw[dept_code]['total'] += 1

            if m_raw.lower() in ['nan', 'unknown', '', 'none']:
                res.update({"status": "BŁĄD DANYCH", "color": "dark", "filter_cat": "unknown"})
                stats['unknown'] += 1
                departments_raw[dept_code]['unknown'] += 1
            else:
                ref = get_db_reference(m_raw)
                if ref:
                    res["latest"] = ref.latest_version
                    res["match_model"] = ref.model_name
                    comp_result = compare_versions(v_pc, ref.latest_version)
                    
                    if comp_result == 0:
                        res.update({"status": "AKTUALNY", "color": "success", "filter_cat": "ok"})
                        stats['ok'] += 1
                        departments_raw[dept_code]['ok'] += 1
                    elif comp_result == 1:
                        res.update({"status": "OK (Nowszy)", "color": "info", "filter_cat": "ok"})
                        stats['newer'] += 1
                        departments_raw[dept_code]['ok'] += 1
                    else:
                        res.update({"status": "NIEAKTUALNY!", "color": "danger", "filter_cat": "danger"})
                        stats['outdated'] += 1
                        departments_raw[dept_code]['outdated'] += 1
                else:
                    res.update({"status": "BRAK WZORCA", "color": "warning", "filter_cat": "warning"})
                    stats['unknown'] += 1
                    departments_raw[dept_code]['unknown'] += 1
            
            q = urllib.parse.quote(f"{m_raw} BIOS driver support")
            res["search_url"] = f"https://www.google.com/search?q={q}"
            rows.append(res)
            
        # Podsumowanie globalne
        stats['total'] = len(rows)
        valid_total = stats['total'] - stats['unknown']
        
        if valid_total > 0:
            outdated_pct = round((stats['outdated'] / valid_total) * 100, 1)
            stats['outdated_pct'] = outdated_pct
            stats['compliance_rate'] = round(((stats['ok'] + stats['newer']) / valid_total) * 100, 1)
            
            if outdated_pct <= 10:
                stats['risk_icon'] = 'bi-emoji-sunglasses'; stats['risk_color'] = 'neon-green'; stats['risk_text'] = 'BUNKIER'
            elif outdated_pct <= 30:
                stats['risk_icon'] = 'bi-emoji-smile'; stats['risk_color'] = 'success'; stats['risk_text'] = 'STABILNY'
            elif outdated_pct <= 60:
                stats['risk_icon'] = 'bi-emoji-neutral'; stats['risk_color'] = 'warning'; stats['risk_text'] = 'OSTRZEGAWCZY'
            else:
                stats['risk_icon'] = 'bi-emoji-dizzy'; stats['risk_color'] = 'danger'; stats['risk_text'] = 'KRYTYCZNY'
        
        # Podsumowanie oddziałów
        final_depts = []
        for name, d_stats in departments_raw.items():
            d_valid = d_stats['total'] - d_stats['unknown']
            score = 0
            if d_valid > 0:
                score = round((d_stats['ok'] / d_valid) * 100, 1)
            
            bar_color = "success"
            if score < 50: bar_color = "danger"
            elif score < 80: bar_color = "warning"
            
            final_depts.append({
                'name': name,
                'total': d_stats['total'],
                'ok': d_stats['ok'],
                'outdated': d_stats['outdated'],
                'unknown': d_stats['unknown'],
                'score': score,
                'bar_color': bar_color
            })
        
        # Sortowanie
        stats['departments'] = sorted(final_depts, key=lambda x: x['score'])
        
        # Dane do wykresu
        sorted_by_size = sorted(final_depts, key=lambda x: x['total'], reverse=True)
        stats['chart_dept_labels'] = ",".join([d['name'] for d in sorted_by_size])
        stats['chart_dept_data'] = ",".join([str(d['total']) for d in sorted_by_size])

        return {'stats': stats, 'rows': rows}
        
    except Exception as e:
        print(f"Logic Error: {e}")
        return None