import os
import io
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
import pandas as pd
from sqlalchemy import func
from models import db, BiosReference
import logic
from threading import Timer
import webbrowser

app = Flask(__name__)
app.secret_key = 'super_secret_cyber_key_999'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bios_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['JSON_DB'] = 'bios_versions.json'

db.init_app(app)

KNOWN_MODELS = [
    "Dell Latitude 5420", "Dell Latitude 5430", "Dell Latitude 7420",
    "HP EliteBook 840 G8", "Lenovo ThinkPad T14 Gen 2"
]

# --- TO JEST FUNKCJA, KTÓREJ BRAKOWAŁO ---
def sync_sql_with_json():
    """Wczytuje JSON do SQL przy starcie i po imporcie"""
    data = logic.load_json_db(app.config['JSON_DB'])
    
    # Pobieramy istniejące wpisy z bazy, żeby nie duplikować zapytań
    existing = {e.model_name: e for e in BiosReference.query.all()}
    
    for model, version in data.items():
        # Prosta heurystyka producenta
        vendor = "Dell" if "Dell" in model else ("Lenovo" if "Lenovo" in model else ("HP" if "HP" in model else "Inny"))
        
        if model in existing:
            # Jeśli wersja się różni, aktualizujemy
            if existing[model].latest_version != version:
                existing[model].latest_version = version
                existing[model].last_checked = datetime.now()
        else:
            # Jeśli nie ma w bazie, dodajemy nowy
            db.session.add(BiosReference(vendor=vendor, model_name=model, latest_version=version))
    
    db.session.commit()
# -----------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    report_data = None
    active_tab = 'scanner'
    
    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            session['last_filepath'] = filepath
            report_data = logic.process_uploaded_file(filepath)
            
            if report_data: flash('Analiza zakończona.', 'success')
            else: flash('Błąd analizy pliku.', 'danger')
            active_tab = 'scanner'

    all_bios = BiosReference.query.order_by(BiosReference.vendor, BiosReference.model_name).all()
    recent_updates = BiosReference.query.order_by(BiosReference.last_checked.desc()).limit(5).all()
    
    return render_template(
        'index.html', report=report_data, db_entries=all_bios, 
        db_count=len(all_bios), known_models=KNOWN_MODELS, 
        active_tab=active_tab, recent_updates=recent_updates,
        now_year=datetime.now().year
    )

@app.route('/manual_add', methods=['POST'])
def manual_add():
    vendor = request.form.get('vendor')
    model = request.form.get('model', '').strip()
    version = request.form.get('version', '').strip()
    
    if not model or not version:
        return redirect(url_for('index', _anchor='admin'))

    full_name = model if (vendor in model or vendor == "Inny") else f"{vendor} {model}"
    
    # Check duplicate (case insensitive)
    exists = BiosReference.query.filter(func.lower(BiosReference.model_name) == func.lower(full_name)).first()
    if exists:
        flash(f'Model "{full_name}" już istnieje! Użyj edycji.', 'warning')
        return redirect(url_for('index', _anchor='admin'))
    
    # JSON Save
    data = logic.load_json_db(app.config['JSON_DB'])
    data[full_name] = version
    logic.save_json_db(app.config['JSON_DB'], data)
    
    # SQL Save
    db.session.add(BiosReference(vendor=vendor, model_name=full_name, latest_version=version, last_checked=datetime.now()))
    db.session.commit()
    
    flash(f'Dodano: {full_name}', 'success')
    return redirect(url_for('index', _anchor='admin'))

@app.route('/edit_entry', methods=['POST'])
def edit_entry():
    entry_id = request.form.get('id')
    new_version = request.form.get('version')
    is_old_state = True if request.form.get('is_old') == 'on' else False
    
    entry = BiosReference.query.get(entry_id)
    
    if entry and new_version:
        # 1. Update JSON
        data = logic.load_json_db(app.config['JSON_DB'])
        if entry.model_name in data:
            data[entry.model_name] = new_version
            logic.save_json_db(app.config['JSON_DB'], data)
            
        # 2. Update SQL
        entry.latest_version = new_version
        entry.is_old = is_old_state
        entry.last_checked = datetime.now()
        db.session.commit()
        
        status_msg = " (Oznaczono jako OLD)" if is_old_state else ""
        flash(f'Zaktualizowano wpis.{status_msg}', 'success')
    else:
        flash('Błąd edycji wpisu.', 'danger')
        
    return redirect(url_for('index', _anchor='admin'))

@app.route('/manual_delete/<int:entry_id>')
def manual_delete(entry_id):
    entry = BiosReference.query.get(entry_id)
    if entry:
        data = logic.load_json_db(app.config['JSON_DB'])
        if entry.model_name in data:
            del data[entry.model_name]
            logic.save_json_db(app.config['JSON_DB'], data)
        db.session.delete(entry)
        db.session.commit()
        flash('Usunięto wpis.', 'info')
    return redirect(url_for('index', _anchor='admin'))

@app.route('/import_json_db', methods=['POST'])
def import_json_db():
    if 'json_file' not in request.files:
        flash('Brak pliku.', 'danger')
        return redirect(url_for('index', _anchor='admin'))
    
    file = request.files['json_file']
    if file.filename == '' or not file.filename.endswith('.json'):
        flash('Wybierz poprawny plik .json', 'danger')
        return redirect(url_for('index', _anchor='admin'))

    try:
        new_data = json.load(file)
        if not isinstance(new_data, dict):
            flash('Błędny format JSON (wymagany słownik "Model": "Wersja").', 'danger')
            return redirect(url_for('index', _anchor='admin'))
        
        # Merge z obecnym JSON
        current_data = logic.load_json_db(app.config['JSON_DB'])
        count_updated = 0
        
        for model, ver in new_data.items():
            # Aktualizujemy lub dodajemy tylko jeśli wersja się różni
            if model not in current_data or current_data[model] != ver:
                current_data[model] = ver
                count_updated += 1
        
        logic.save_json_db(app.config['JSON_DB'], current_data)
        
        # TUTAJ WYWOŁUJEMY FUNKCJĘ, KTÓRA WCZEŚNIEJ POWODOWAŁA BŁĄD
        sync_sql_with_json() 
        
        flash(f'Zaimportowano pomyślnie. Zaktualizowano/dodano: {count_updated} modeli.', 'success')
        
    except Exception as e:
        flash(f'Błąd importu: {e}', 'danger')

    return redirect(url_for('index', _anchor='admin'))

@app.route('/export_report')
def export_report():
    filepath = session.get('last_filepath')
    if not filepath or not os.path.exists(filepath): 
        flash('Sesja wygasła lub plik usunięty. Wgraj plik ponownie.', 'warning')
        return redirect(url_for('index'))
        
    data = logic.process_uploaded_file(filepath)
    if not data: return redirect(url_for('index'))

    export_rows = [{"Nazwa": r['computer_name'], "Model": r['model'], "Tag": r['service_tag'], "Ver PC": r['current'], "Ver Baza": r['latest'], "Status": r['status']} for r in data['rows']]
    
    buffer = io.BytesIO()
    pd.DataFrame(export_rows).to_csv(buffer, index=False, sep=';', encoding='utf-8-sig')
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Raport_BIOS_{datetime.now().strftime('%Y%m%d')}.csv", mimetype='text/csv')

@app.route('/download_db')
def download_db():
    return send_file(app.config['JSON_DB'], as_attachment=True) if os.path.exists(app.config['JSON_DB']) else redirect(url_for('index'))

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        sync_sql_with_json()
    
    Timer(1, open_browser).start()
    app.run(port=5000, debug=False)